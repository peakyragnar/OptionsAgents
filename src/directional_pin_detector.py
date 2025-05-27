#!/usr/bin/env python3
"""
Directional 0DTE Pin Detection System
Real-time directional gamma positioning analysis for options premium sellers
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
import json
from collections import defaultdict
import sqlite3

@dataclass
class PinData:
    strike: float
    force: float
    volume: int
    direction: str  # 'UPWARD', 'DOWNWARD', 'NEUTRAL'

@dataclass
class DirectionalAnalysis:
    spx_level: float
    upward_pin: Optional[PinData]
    downward_pin: Optional[PinData]
    strongest_neutral: Optional[PinData]
    net_directional_force: float
    expected_direction: str
    strongest_overall: str
    confidence: float

class DirectionalPinDetector:
    """
    Detects directional gamma pin formations in 0DTE options
    
    Key Concepts:
    - Calls above SPX = Upward pin force (dealers buy stock to hedge)
    - Puts below SPX = Downward pin force (dealers sell stock to hedge)  
    - ATM options = Neutral pin force (can pull either direction)
    """
    
    def __init__(self, atm_threshold: float = 5.0):
        self.positions = defaultdict(lambda: {
            'call_volume': 0,
            'put_volume': 0,
            'call_short_volume': 0,
            'put_short_volume': 0,
            'gamma': 0,
            'last_price': 0,
            'total_trades': 0
        })
        
        self.atm_threshold = atm_threshold  # ±$5 considered ATM
        self.spx_level = 5800  # Will be updated from snapshots
        self.trade_history = []
        self.spike_detector = SpikeDetector()
        
        # Initialize database for backtesting
        self.init_database()
    
    def init_database(self):
        """Initialize SQLite database for storing pin analysis"""
        self.conn = sqlite3.connect('data/pin_analysis.db', check_same_thread=False)
        self.conn.execute('''
            CREATE TABLE IF NOT EXISTS pin_analysis (
                timestamp TEXT,
                spx_level REAL,
                upward_pin_strike REAL,
                upward_pin_force REAL,
                downward_pin_strike REAL,
                downward_pin_force REAL,
                net_directional_force REAL,
                expected_direction TEXT,
                confidence REAL
            )
        ''')
        self.conn.commit()
    
    def update_spx_level(self, new_level: float):
        """Update current SPX level from snapshots"""
        self.spx_level = new_level
    
    def process_trade(self, trade_data: Dict):
        """
        Process incoming options trade and update pin analysis
        
        Args:
            trade_data: {
                'symbol': 'O:SPXW250523C05850000',
                'price': 2.15,
                'size': 5,
                'timestamp': 1684234567890,
                'conditions': ['37']  # Trade conditions
            }
        """
        symbol = trade_data.get('symbol', '')
        if not self._is_spx_option(symbol):
            return
        
        strike = self._extract_strike(symbol)
        if not strike:
            return
        
        is_call = 'C' in symbol
        price = trade_data.get('price', 0)
        size = trade_data.get('size', 0)
        timestamp = trade_data.get('timestamp', 0)
        
        # Classify trade as buy/sell (simplified - you have better logic)
        is_short_trade = self._classify_as_short_trade(trade_data, is_call, strike)
        
        # Update position tracking
        pos = self.positions[strike]
        pos['last_price'] = price
        pos['total_trades'] += 1
        
        if is_call:
            pos['call_volume'] += size
            if is_short_trade:
                pos['call_short_volume'] += size
        else:
            pos['put_volume'] += size  
            if is_short_trade:
                pos['put_short_volume'] += size
        
        # Update gamma (simplified - use your Black-Scholes calculation)
        pos['gamma'] = self._estimate_gamma(strike, is_call)
        
        # Store trade for spike detection
        trade_record = {
            'timestamp': timestamp,
            'strike': strike,
            'size': size,
            'is_call': is_call,
            'is_short': is_short_trade,
            'price': price
        }
        self.trade_history.append(trade_record)
        self.spike_detector.add_trade(trade_record)
        
        # Keep only recent trades (last 2 hours)
        cutoff = timestamp - (2 * 60 * 60 * 1000)
        self.trade_history = [t for t in self.trade_history if t['timestamp'] > cutoff]
    
    def get_directional_analysis(self) -> DirectionalAnalysis:
        """
        Calculate directional gamma pin analysis
        
        Returns:
            DirectionalAnalysis with upward/downward pins and net force
        """
        upward_forces = {}    # Calls above SPX  
        downward_forces = {}  # Puts below SPX
        neutral_forces = {}   # ATM options
        
        for strike, data in self.positions.items():
            if not data['total_trades']:  # Skip empty strikes
                continue
                
            if strike > self.spx_level + self.atm_threshold:
                # Calls above SPX create upward pin force
                if data['call_short_volume'] > 0:
                    force = data['call_short_volume'] * data['gamma'] * 100
                    upward_forces[strike] = force
                    
            elif strike < self.spx_level - self.atm_threshold:
                # Puts below SPX create downward pin force  
                if data['put_short_volume'] > 0:
                    force = data['put_short_volume'] * data['gamma'] * 100
                    downward_forces[strike] = force
                    
            else:
                # ATM options can pin in either direction
                total_short = data['call_short_volume'] + data['put_short_volume']
                if total_short > 0:
                    force = total_short * data['gamma'] * 100
                    neutral_forces[strike] = force
        
        # Find strongest pins
        upward_pin = None
        if upward_forces:
            strike, force = max(upward_forces.items(), key=lambda x: x[1])
            upward_pin = PinData(strike, force, self.positions[strike]['call_short_volume'], 'UPWARD')
        
        downward_pin = None  
        if downward_forces:
            strike, force = max(downward_forces.items(), key=lambda x: x[1])
            downward_pin = PinData(strike, force, self.positions[strike]['put_short_volume'], 'DOWNWARD')
        
        strongest_neutral = None
        if neutral_forces:
            strike, force = max(neutral_forces.items(), key=lambda x: x[1])
            total_vol = self.positions[strike]['call_short_volume'] + self.positions[strike]['put_short_volume']
            strongest_neutral = PinData(strike, force, total_vol, 'NEUTRAL')
        
        # Calculate net directional force
        net_force = sum(upward_forces.values()) - sum(downward_forces.values())
        
        # Determine expected direction
        if abs(net_force) < 10000:
            expected_direction = 'SIDEWAYS'
            strongest_overall = f"RANGE_BOUND_{self.spx_level:.0f}"
        elif net_force > 0:
            expected_direction = 'UPWARD_DRIFT'
            target = upward_pin.strike if upward_pin else self.spx_level + 10
            strongest_overall = f"TARGET_{target:.0f}"
        else:
            expected_direction = 'DOWNWARD_DRIFT'  
            target = downward_pin.strike if downward_pin else self.spx_level - 10
            strongest_overall = f"TARGET_{target:.0f}"
        
        # Calculate confidence based on force magnitude
        max_force = max([
            upward_pin.force if upward_pin else 0,
            downward_pin.force if downward_pin else 0,
            strongest_neutral.force if strongest_neutral else 0
        ])
        confidence = min(max_force / 100000, 1.0)  # Scale to 0-1
        
        analysis = DirectionalAnalysis(
            spx_level=self.spx_level,
            upward_pin=upward_pin,
            downward_pin=downward_pin,
            strongest_neutral=strongest_neutral,
            net_directional_force=net_force,
            expected_direction=expected_direction,
            strongest_overall=strongest_overall,
            confidence=confidence
        )
        
        # Store to database
        self._store_analysis(analysis)
        
        return analysis
    
    def get_agent_summary(self) -> Dict:
        """
        Get structured data for AI agents to consume
        
        Returns:
            Dictionary with all pin analysis data
        """
        analysis = self.get_directional_analysis()
        spikes = self.spike_detector.get_recent_spikes()
        
        return {
            'timestamp': datetime.now().isoformat(),
            'spx_level': analysis.spx_level,
            'upward_pin': {
                'strike': analysis.upward_pin.strike,
                'force': analysis.upward_pin.force,
                'volume': analysis.upward_pin.volume
            } if analysis.upward_pin else None,
            'downward_pin': {
                'strike': analysis.downward_pin.strike,
                'force': analysis.downward_pin.force,
                'volume': analysis.downward_pin.volume
            } if analysis.downward_pin else None,
            'strongest_neutral': {
                'strike': analysis.strongest_neutral.strike,
                'force': analysis.strongest_neutral.force,
                'volume': analysis.strongest_neutral.volume
            } if analysis.strongest_neutral else None,
            'net_directional_force': analysis.net_directional_force,
            'expected_direction': analysis.expected_direction,
            'strongest_overall': analysis.strongest_overall,
            'confidence': analysis.confidence,
            'recent_spikes': spikes,
            'risk_level': self._calculate_risk_level(analysis),
            'trading_recommendation': self._get_trading_recommendation(analysis)
        }
    
    def print_human_dashboard(self):
        """Print human-readable pin analysis dashboard"""
        analysis = self.get_directional_analysis()
        spikes = self.spike_detector.get_recent_spikes()
        
        print(f"\n🎯 DIRECTIONAL PIN ANALYSIS - {datetime.now().strftime('%H:%M:%S')}")
        print(f"SPX Level: {analysis.spx_level:.2f}")
        print(f"Confidence: {analysis.confidence:.1%}")
        
        if analysis.upward_pin:
            print(f"\n📈 UPWARD PINS (Calls Above SPX):")
            print(f"  {analysis.upward_pin.strike}: {analysis.upward_pin.force:,.0f} gamma units ← STRONGEST UPWARD")
            
        if analysis.downward_pin:
            print(f"\n📉 DOWNWARD PINS (Puts Below SPX):")
            print(f"  {analysis.downward_pin.strike}: {analysis.downward_pin.force:,.0f} gamma units ← STRONGEST DOWNWARD")
            
        if analysis.strongest_neutral:
            print(f"\n⚖️  NEUTRAL PINS (ATM):")
            print(f"  {analysis.strongest_neutral.strike}: {analysis.strongest_neutral.force:,.0f} gamma units")
        
        print(f"\n🎯 NET FORCE: {analysis.net_directional_force:+,.0f} ({analysis.expected_direction})")
        print(f"🎯 TARGET: {analysis.strongest_overall}")
        
        if spikes:
            print(f"\n⚡ RECENT SPIKES:")
            for spike in spikes[-3:]:
                print(f"  {spike['strike']}: +{spike['volume']} contracts ({spike['time']})")
        
        print("-" * 60)
    
    def _is_spx_option(self, symbol: str) -> bool:
        """Check if symbol is SPX option"""
        return symbol.startswith('O:SPX')
    
    def _extract_strike(self, symbol: str) -> Optional[float]:
        """Extract strike price from option symbol"""
        try:
            # Format: O:SPXW250523C05850000
            parts = symbol.split('C')
            if len(parts) != 2:
                parts = symbol.split('P')
            if len(parts) == 2:
                strike_str = parts[1][:8]  # First 8 digits
                return float(strike_str) / 1000  # Convert to actual strike
        except:
            pass
        return None
    
    def _classify_as_short_trade(self, trade_data: Dict, is_call: bool, strike: float) -> bool:
        """
        Classify trade as premium selling (simplified)
        You should replace this with your proven classification logic
        """
        price = trade_data.get('price', 0)
        size = trade_data.get('size', 0)
        
        # Simple heuristics (replace with your logic)
        if size >= 10:  # Large trades more likely short
            return True
        if is_call and strike > self.spx_level + 20:  # Far OTM calls often sold
            return True
        if not is_call and strike < self.spx_level - 20:  # Far OTM puts often sold
            return True
        
        return False
    
    def _estimate_gamma(self, strike: float, is_call: bool) -> float:
        """
        Estimate gamma (simplified - use your Black-Scholes calculation)
        """
        distance = abs(strike - self.spx_level)
        if distance < 10:
            return 0.008  # High gamma ATM
        elif distance < 25:
            return 0.004  # Medium gamma
        else:
            return 0.001  # Low gamma OTM
    
    def _calculate_risk_level(self, analysis: DirectionalAnalysis) -> str:
        """Calculate risk level based on pin strength"""
        max_force = max([
            analysis.upward_pin.force if analysis.upward_pin else 0,
            analysis.downward_pin.force if analysis.downward_pin else 0
        ])
        
        if max_force > 500000:
            return 'EXTREME'
        elif max_force > 200000:
            return 'HIGH'
        elif max_force > 50000:
            return 'MEDIUM'
        else:
            return 'LOW'
    
    def _get_trading_recommendation(self, analysis: DirectionalAnalysis) -> str:
        """Get trading recommendation for agents"""
        if analysis.confidence < 0.3:
            return 'NO_ACTION_LOW_CONFIDENCE'
        
        if analysis.expected_direction == 'UPWARD_DRIFT':
            return f'EXPECT_DRIFT_TO_{analysis.upward_pin.strike if analysis.upward_pin else int(analysis.spx_level + 10)}'
        elif analysis.expected_direction == 'DOWNWARD_DRIFT':
            return f'EXPECT_DRIFT_TO_{analysis.downward_pin.strike if analysis.downward_pin else int(analysis.spx_level - 10)}'
        else:
            return 'EXPECT_SIDEWAYS_ACTION'
    
    def _store_analysis(self, analysis: DirectionalAnalysis):
        """Store analysis to database for backtesting"""
        self.conn.execute('''
            INSERT INTO pin_analysis VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            datetime.now().isoformat(),
            analysis.spx_level,
            analysis.upward_pin.strike if analysis.upward_pin else None,
            analysis.upward_pin.force if analysis.upward_pin else None,
            analysis.downward_pin.strike if analysis.downward_pin else None,
            analysis.downward_pin.force if analysis.downward_pin else None,
            analysis.net_directional_force,
            analysis.expected_direction,
            analysis.confidence
        ))
        self.conn.commit()

class SpikeDetector:
    """Detects sudden volume spikes at specific strikes"""
    
    def __init__(self, spike_window_minutes: int = 5):
        self.trades = []
        self.spike_window = spike_window_minutes * 60 * 1000  # Convert to milliseconds
        
    def add_trade(self, trade: Dict):
        """Add trade for spike detection"""
        self.trades.append(trade)
        
        # Keep only recent trades
        cutoff = trade['timestamp'] - self.spike_window
        self.trades = [t for t in self.trades if t['timestamp'] > cutoff]
    
    def get_recent_spikes(self) -> List[Dict]:
        """Get recent volume spikes"""
        if not self.trades:
            return []
        
        # Group by strike and calculate volume
        strike_volumes = defaultdict(int)
        for trade in self.trades:
            if trade['is_short']:  # Only count short trades
                strike_volumes[trade['strike']] += trade['size']
        
        # Find spikes (simplified - volume > 20 in recent window)
        spikes = []
        for strike, volume in strike_volumes.items():
            if volume >= 20:
                recent_trade = max([t for t in self.trades if t['strike'] == strike], 
                                 key=lambda x: x['timestamp'])
                spikes.append({
                    'strike': strike,
                    'volume': volume,
                    'time': datetime.fromtimestamp(recent_trade['timestamp']/1000).strftime('%H:%M:%S')
                })
        
        return sorted(spikes, key=lambda x: x['volume'], reverse=True)

# Global instance for your streaming system
DIRECTIONAL_PIN_DETECTOR = DirectionalPinDetector()

def get_pin_analysis_for_agents() -> Dict:
    """Easy function for agents to call"""
    return DIRECTIONAL_PIN_DETECTOR.get_agent_summary()

def print_pin_dashboard():
    """Easy function to print human dashboard"""
    DIRECTIONAL_PIN_DETECTOR.print_human_dashboard()

if __name__ == "__main__":
    # Test the system
    detector = DirectionalPinDetector()
    detector.update_spx_level(5847.50)
    
    # Simulate some trades
    test_trades = [
        {'symbol': 'O:SPXW250523C05860000', 'price': 2.15, 'size': 25, 'timestamp': 1684234567890},
        {'symbol': 'O:SPXW250523P05830000', 'price': 1.85, 'size': 15, 'timestamp': 1684234567891},
        {'symbol': 'O:SPXW250523C05850000', 'price': 3.20, 'size': 8, 'timestamp': 1684234567892},
    ]
    
    for trade in test_trades:
        detector.process_trade(trade)
    
    # Show results
    detector.print_human_dashboard()
    
    # Show agent data
    agent_data = detector.get_agent_summary()
    print(f"\nAgent Data: {json.dumps(agent_data, indent=2)}")
