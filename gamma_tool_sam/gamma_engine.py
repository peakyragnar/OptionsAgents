"""
Gamma Engine - Main orchestrator for Gamma Tool Sam
Provides both human dashboard and agent API interfaces
"""

import asyncio
from datetime import datetime
from typing import Dict, List, Optional
import json
from collections import defaultdict

from .core.trade_processor import TradeProcessor
from .core.gamma_calculator import GammaCalculator
from .core.position_tracker import PositionTracker
from .core.change_detector import ChangeDetector
from .core.confidence_calculator import ConfidenceCalculator, MarketConditions

class GammaEngine:
    """
    Main engine that orchestrates all components
    Provides dual interfaces for humans and agents
    """
    
    def __init__(self, spx_price: Optional[float] = None):
        # Core components
        self.trade_processor = TradeProcessor()
        self.gamma_calculator = GammaCalculator()
        self.position_tracker = PositionTracker()
        self.change_detector = ChangeDetector()
        self.confidence_calculator = ConfidenceCalculator()
        
        # Set initial SPX price if provided
        if spx_price:
            self.gamma_calculator.update_spx_price(spx_price)
            
        # Register trade callback
        self.trade_processor.register_callback(self._process_trade)
        
        # Analysis state
        self.last_analysis = None
        self.analysis_timestamp = None
        
    def _process_trade(self, trade):
        """Process each incoming trade through the pipeline"""
        # Calculate gamma
        gamma_result = self.gamma_calculator.calculate_trade_gamma(trade)
        if not gamma_result:
            return
            
        # Update positions
        self.position_tracker.update_position(trade, gamma_result)
        
        # Detect changes
        changes = self.change_detector.update(
            trade, gamma_result, self.position_tracker
        )
        
        # Update analysis
        self._update_analysis()
        
    def _update_analysis(self):
        """Update current analysis state"""
        # Get all positions
        positions = self.position_tracker.get_all_positions()
        
        # Get top pins
        top_upward = self.position_tracker.get_top_pins(n=3, direction='UPWARD')
        top_downward = self.position_tracker.get_top_pins(n=3, direction='DOWNWARD')
        top_all = self.position_tracker.get_top_pins(n=5)
        
        # Calculate net forces
        if not positions.empty:
            upward_force = positions[positions['net_gamma'] > 0]['net_gamma'].sum()
            downward_force = abs(positions[positions['net_gamma'] < 0]['net_gamma'].sum())
            net_force = upward_force - downward_force
        else:
            net_force = 0
            upward_force = 0
            downward_force = 0
            
        # Get primary pin
        if not top_all.empty:
            primary_pin = {
                'strike': int(top_all.iloc[0]['strike']),
                'force': float(top_all.iloc[0]['total_gamma_force']),
                'direction': top_all.iloc[0]['direction']
            }
        else:
            primary_pin = None
            
        # Generate trading signal
        signal = self._generate_signal(net_force, primary_pin)
        
        # Get active alerts
        alerts = self.change_detector.get_active_alerts()
        
        # Prepare data for confidence calculation
        analysis_data = {
            'net_force': net_force,
            'upward_force': upward_force,
            'downward_force': downward_force,
            'direction': 'UP' if net_force > 0 else 'DOWN',
            'primary_pin': primary_pin,
            'spx_price': self.gamma_calculator.spx_price,
            'all_pins': self._format_pins(top_all),
            'active_alerts': alerts
        }
        
        # Calculate sophisticated confidence
        confidence, confidence_details = self.confidence_calculator.calculate_confidence(analysis_data)
        
        # Build analysis
        self.last_analysis = {
            'timestamp': datetime.now(),
            'spx_price': self.gamma_calculator.spx_price,
            'net_force': net_force,
            'upward_force': upward_force,
            'downward_force': downward_force,
            'direction': 'UP' if net_force > 0 else 'DOWN',
            'confidence': confidence,
            'confidence_details': confidence_details,
            'primary_pin': primary_pin,
            'top_upward_pins': self._format_pins(top_upward),
            'top_downward_pins': self._format_pins(top_downward),
            'signal': signal,
            'active_alerts': self._format_alerts(alerts),
            'stats': self.trade_processor.get_stats()
        }
        
        self.analysis_timestamp = datetime.now()
        
        # Update database
        self.position_tracker.update_analysis_state(self.last_analysis)
        
    def _generate_signal(self, net_force: float, primary_pin: Optional[Dict]) -> Dict:
        """Generate trading signal based on current state"""
        if not primary_pin or not self.gamma_calculator.spx_price:
            return {'action': 'WAIT', 'reason': 'Insufficient data'}
            
        spx = self.gamma_calculator.spx_price
        target = primary_pin['strike']
        distance = target - spx
        
        # Determine action based on net force and distance
        if abs(net_force) < 100000:  # Low conviction
            return {
                'action': 'WAIT',
                'reason': 'Low gamma concentration',
                'confidence': 0.3
            }
            
        if net_force > 0:  # Upward pressure
            if distance > 0 and distance < 20:  # Target above, reasonable distance
                return {
                    'action': 'LONG',
                    'entry': spx,
                    'target': target,
                    'stop': spx - 5,
                    'reason': f'Strong upward pin at {target}',
                    'confidence': min(abs(net_force) / 500000, 0.9)
                }
        else:  # Downward pressure
            if distance < 0 and distance > -20:  # Target below, reasonable distance
                return {
                    'action': 'SHORT',
                    'entry': spx,
                    'target': target,
                    'stop': spx + 5,
                    'reason': f'Strong downward pin at {target}',
                    'confidence': min(abs(net_force) / 500000, 0.9)
                }
                
        return {
            'action': 'WAIT',
            'reason': 'Pin too far from current price',
            'confidence': 0.4
        }
        
    def _format_pins(self, pins_df) -> List[Dict]:
        """Format pins dataframe for output"""
        if pins_df.empty:
            return []
            
        pins = []
        for _, row in pins_df.iterrows():
            pins.append({
                'strike': int(row['strike']),
                'force': float(row['total_gamma_force']),
                'volume': int(row['total_volume']),
                'direction': row.get('direction', 'UNKNOWN')
            })
        return pins
        
    def _format_alerts(self, alerts: List) -> List[Dict]:
        """Format alerts for output"""
        formatted = []
        for alert in alerts[:10]:  # Limit to 10 most recent
            formatted.append({
                'timestamp': alert.timestamp.isoformat(),
                'type': alert.change_type,
                'strike': alert.strike,
                'magnitude': alert.magnitude,
                'severity': alert.severity,
                'details': alert.details
            })
        return formatted
        
    # ========== AGENT API INTERFACE ==========
    
    def get_pin_summary(self) -> Dict:
        """Complete analysis data for agents"""
        if not self.last_analysis:
            return {'error': 'No analysis available yet'}
            
        return self.last_analysis
    
    def get_strongest_pin(self) -> Optional[Dict]:
        """Just the top pin for quick decisions"""
        if not self.last_analysis:
            return None
            
        return self.last_analysis.get('primary_pin')
    
    def get_directional_pins(self, direction: str = 'UPWARD') -> List[Dict]:
        """Get pins by direction"""
        if not self.last_analysis:
            return []
            
        if direction == 'UPWARD':
            return self.last_analysis.get('top_upward_pins', [])
        else:
            return self.last_analysis.get('top_downward_pins', [])
    
    def calculate_risk_level(self) -> Dict:
        """Risk assessment based on pin configuration"""
        if not self.last_analysis:
            return {'risk_level': 'UNKNOWN', 'reason': 'No data'}
            
        # Check for strong opposing forces
        up_force = self.last_analysis['upward_force']
        down_force = self.last_analysis['downward_force']
        
        if up_force > 0 and down_force > 0:
            ratio = min(up_force, down_force) / max(up_force, down_force)
            
            if ratio > 0.7:
                return {
                    'risk_level': 'HIGH',
                    'reason': 'Strong opposing pin forces',
                    'volatility_expected': True,
                    'up_force': up_force,
                    'down_force': down_force
                }
                
        # Check for alerts
        critical_alerts = [a for a in self.last_analysis.get('active_alerts', []) 
                          if a['severity'] == 'CRITICAL']
        
        if critical_alerts:
            return {
                'risk_level': 'HIGH',
                'reason': f'{len(critical_alerts)} critical alerts active',
                'alerts': critical_alerts
            }
            
        return {
            'risk_level': 'NORMAL',
            'reason': 'Normal market conditions',
            'confidence': self.last_analysis.get('confidence', 0)
        }
    
    def get_recent_spikes(self, minutes: int = 5) -> List[Dict]:
        """Get recent volume/gamma spikes"""
        if not self.last_analysis:
            return []
            
        spikes = [a for a in self.last_analysis.get('active_alerts', [])
                  if a['type'] == 'SPIKE']
        
        return spikes
    
    # ========== HUMAN DASHBOARD INTERFACE ==========
    
    def print_human_dashboard(self):
        """Visual dashboard for human operators"""
        if not self.last_analysis:
            print("❌ No analysis data available yet")
            return
            
        a = self.last_analysis
        
        print("\n" + "═" * 60)
        print(f"🎯 GAMMA TOOL SAM | SPX: ${a['spx_price']:,.2f} | {a['timestamp'].strftime('%H:%M:%S')}")
        print("═" * 60)
        
        # Direction and force
        arrow = "↑" if a['direction'] == 'UP' else "↓"
        print(f"\nDIRECTIONAL FORCE: {a['net_force']:+,.0f} {arrow} {a['direction']}WARD")
        
        # Primary target
        if a['primary_pin']:
            pin = a['primary_pin']
            distance = pin['strike'] - a['spx_price']
            print(f"Primary Target: {pin['strike']} ({distance:+.0f}pts away)")
            
        # Confidence meter with details
        conf_bars = int(a['confidence'] * 10)
        print(f"Confidence: {'█' * conf_bars}{'░' * (10 - conf_bars)} {a['confidence']:.0%}")
        
        # Show confidence breakdown if available
        if 'confidence_details' in a:
            details = a['confidence_details']
            if 'explanation' in details:
                print(f"Analysis: {' | '.join(details['explanation'][:3])}")
        
        # Top pins
        print("\nTOP PINS:")
        
        # Upward pins
        if a['top_upward_pins']:
            print("↑ UPWARD:")
            for pin in a['top_upward_pins'][:3]:
                force_bars = int(pin['force'] / 100000)
                print(f"  {pin['strike']}: {'█' * min(force_bars, 8)} {pin['force']:,.0f}")
                
        # Downward pins
        if a['top_downward_pins']:
            print("↓ DOWNWARD:")
            for pin in a['top_downward_pins'][:3]:
                force_bars = int(pin['force'] / 100000)
                print(f"  {pin['strike']}: {'█' * min(force_bars, 8)} {pin['force']:,.0f}")
        
        # Alerts
        if a['active_alerts']:
            print("\n⚡ ALERTS (Last 5min):")
            for alert in a['active_alerts'][:5]:
                icon = {'CRITICAL': '🚨', 'HIGH': '⚠️', 'MEDIUM': '📊'}.get(alert['severity'], 'ℹ️')
                
                if alert['type'] == 'SPIKE':
                    print(f"{icon} SPIKE: {alert['details']['volume']}x {alert['strike']}{alert['details']['option_type'][0]} @ {datetime.fromisoformat(alert['timestamp']).strftime('%H:%M')} (+{alert['details']['gamma_added']:,.0f})")
                elif alert['type'] == 'DIRECTION_FLIP':
                    print(f"{icon} DIRECTION FLIP: {alert['details']['from']} → {alert['details']['to']}")
                elif alert['type'] == 'NEW_PIN':
                    print(f"{icon} NEW PIN: {alert['strike']} growing rapidly ({alert['magnitude']:.1f}x)")
                    
        # Trading signal
        signal = a['signal']
        if signal['action'] != 'WAIT':
            print(f"\nSIGNAL: {signal['action']} → {signal.get('target', 'N/A')} | Stop: {signal.get('stop', 'N/A')}")
        else:
            print(f"\nSIGNAL: {signal['action']} - {signal['reason']}")
            
        # Stats
        stats = a['stats']
        print(f"\nStats: {stats['trades_processed']} trades | {stats['strikes_active']} active strikes")
        
        print("═" * 60)
        
    def get_dashboard_data(self) -> Dict:
        """Get dashboard data for web/GUI display"""
        if not self.last_analysis:
            return {'status': 'waiting_for_data'}
            
        return {
            'timestamp': self.last_analysis['timestamp'].isoformat(),
            'spx_price': self.last_analysis['spx_price'],
            'net_force': self.last_analysis['net_force'],
            'direction': self.last_analysis['direction'],
            'confidence': self.last_analysis['confidence'],
            'confidence_details': self.last_analysis.get('confidence_details', {}),
            'primary_pin': self.last_analysis['primary_pin'],
            'pins': {
                'upward': self.last_analysis['top_upward_pins'],
                'downward': self.last_analysis['top_downward_pins']
            },
            'alerts': self.last_analysis['active_alerts'],
            'signal': self.last_analysis['signal'],
            'stats': self.last_analysis['stats']
        }
    
    def get_confidence_analysis(self) -> Dict:
        """Get detailed confidence breakdown"""
        if not self.last_analysis or 'confidence_details' not in self.last_analysis:
            return {'error': 'No confidence analysis available'}
            
        details = self.last_analysis['confidence_details']
        components = details.get('components', {})
        
        return {
            'overall_confidence': self.last_analysis['confidence'],
            'components': {
                'force': {'score': components.get('force_score', 0), 'weight': 0.30},
                'imbalance': {'score': components.get('imbalance_score', 0), 'weight': 0.25},
                'concentration': {'score': components.get('concentration_score', 0), 'weight': 0.20},
                'distance': {'score': components.get('distance_score', 0), 'weight': 0.15},
                'momentum': {'score': components.get('momentum_score', 0), 'weight': 0.10}
            },
            'patterns': details.get('patterns', []),
            'explanation': details.get('explanation', []),
            'market_conditions': details.get('market_conditions', {}),
            'adjustments': details.get('adjustments', {})
        }