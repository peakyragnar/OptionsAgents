"""
Enhanced Pin Detection System - Working Version
"""

import numpy as np
import os
from datetime import datetime, timedelta
from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

@dataclass
class Trade:
    """Trade data structure"""
    symbol: str
    strike: float
    price: float
    volume: int
    timestamp: datetime
    is_call: bool
    underlying_price: float

@dataclass
class MomentumSignal:
    """Momentum signal data structure"""
    signal_type: str
    strike: Optional[float]
    strikes: Optional[List[float]]
    direction: str
    strength: float
    description: str
    timestamp: datetime

class EnhancedPinDetector:
    """Enhanced Pin Detection System"""
    
    def __init__(self, db_path: str = "data/enhanced_pins.db"):
        self.db_path = db_path
        
        # Create data directory if it doesn't exist
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        
        # Core data structures
        self.strikes = defaultdict(lambda: {
            'net_gamma': 0.0,
            'total_volume': 0,
            'call_volume': 0,
            'put_volume': 0,
            'recent_activity': deque(maxlen=50),
            'last_update': datetime.now()
        })
        
        # Momentum tracking
        self.momentum_tracker = deque(maxlen=200)
        self.recent_signals = deque(maxlen=20)
        
        # State
        self.current_spx_level = 0.0
        self.last_spx_update = None
        self.total_trades_processed = 0
        
        # Configuration
        self.config = {
            'min_gamma_threshold': 1.0,
            'min_volume_threshold': 1,
            'acceleration_threshold': 1.5,
        }
        
        print(f"🎯 Enhanced Pin Detector initialized (DB: {db_path})")
    
    def update_spx_level(self, new_level: float, source: str = "unknown"):
        """Update current SPX level"""
        if new_level <= 0:
            return
            
        old_level = self.current_spx_level
        self.current_spx_level = new_level
        self.last_spx_update = datetime.now()
        
        if abs(new_level - old_level) > 1.0:
            print(f"🔍 SPX UPDATE: {old_level:.2f} → {new_level:.2f} (source: {source})")
    
    def process_trade(self, trade: Trade):
        """Process individual trade"""
        self.total_trades_processed += 1
        
        # Calculate gamma
        gamma = self.calculate_trade_gamma(trade)
        
        # Update strike data
        strike_data = self.strikes[trade.strike]
        
        # Apply directional gamma logic
        if trade.is_call and trade.strike > self.current_spx_level:
            strike_data['net_gamma'] += gamma
        elif not trade.is_call and trade.strike < self.current_spx_level:
            strike_data['net_gamma'] += gamma
        
        # Update volume
        strike_data['total_volume'] += trade.volume
        if trade.is_call:
            strike_data['call_volume'] += trade.volume
        else:
            strike_data['put_volume'] += trade.volume
            
        # Add to recent activity
        activity_record = {
            'timestamp': trade.timestamp,
            'volume': trade.volume,
            'price': trade.price,
            'is_call': trade.is_call,
            'gamma': gamma
        }
        strike_data['recent_activity'].append(activity_record)
        strike_data['last_update'] = trade.timestamp
        
        # Update momentum tracker
        momentum_record = {
            'timestamp': trade.timestamp,
            'strike': trade.strike,
            'volume': trade.volume,
            'is_call': trade.is_call,
            'underlying_price': trade.underlying_price
        }
        self.momentum_tracker.append(momentum_record)
    
    def calculate_trade_gamma(self, trade: Trade) -> float:
        """Calculate gamma approximation"""
        strike = trade.strike
        spot = trade.underlying_price
        
        if strike == 0:
            return 0.0
            
        moneyness = spot / strike
        
        if 0.95 <= moneyness <= 1.05:  # Near ATM
            gamma_base = 0.02
        elif 0.90 <= moneyness <= 1.10:  # Close to ATM
            gamma_base = 0.015
        else:  # Far from ATM
            gamma_base = 0.005
            
        return gamma_base * trade.volume
    
    def calculate_enhanced_confidence(self) -> Dict[str, float]:
        """Calculate confidence system"""
        static_confidence = self._calculate_static_confidence()
        momentum_confidence = self._calculate_momentum_confidence()
        
        total_confidence = (static_confidence * 0.6 + momentum_confidence * 0.4)
        
        return {
            'total': total_confidence,
            'static_pin': static_confidence,
            'momentum': momentum_confidence
        }
    
    def _calculate_static_confidence(self) -> float:
        """Static pin confidence"""
        active_strikes = {k: v for k, v in self.strikes.items() 
                         if v['total_volume'] >= self.config['min_volume_threshold']}
        
        if not active_strikes:
            return 0.1
            
        gamma_values = [abs(data['net_gamma']) for data in active_strikes.values()]
        
        if len(gamma_values) < 2:
            return 0.3
            
        gamma_mean = np.mean(gamma_values)
        gamma_std = np.std(gamma_values)
        
        if gamma_mean == 0:
            return 0.1
            
        cv = gamma_std / gamma_mean
        concentration = max(0, 1 - min(cv / 2, 1))
        
        return max(concentration, 0.1)
    
    def _calculate_momentum_confidence(self) -> float:
        """Momentum confidence"""
        if len(self.momentum_tracker) < 10:
            return 0.2
            
        cutoff_time = datetime.now() - timedelta(minutes=3)
        recent_trades = [t for t in self.momentum_tracker if t['timestamp'] > cutoff_time]
        
        if len(recent_trades) < 5:
            return 0.2
            
        above_spx_volume = sum(t['volume'] for t in recent_trades if t['strike'] > self.current_spx_level)
        below_spx_volume = sum(t['volume'] for t in recent_trades if t['strike'] <= self.current_spx_level)
        
        total_volume = above_spx_volume + below_spx_volume
        
        if total_volume == 0:
            return 0.2
            
        bias_ratio = max(above_spx_volume, below_spx_volume) / total_volume
        
        if bias_ratio > 0.7:
            return 0.8
        elif bias_ratio > 0.6:
            return 0.6
        else:
            return 0.3
    
    def get_primary_pin_target(self) -> Tuple[float, float]:
        """Get primary pin target"""
        if not self.strikes:
            return 0.0, 0.0
            
        best_strike = 0.0
        best_gamma = 0.0
        
        for strike, data in self.strikes.items():
            gamma = abs(data['net_gamma'])
            if (gamma > best_gamma and 
                gamma >= self.config['min_gamma_threshold'] and
                data['total_volume'] >= self.config['min_volume_threshold']):
                best_strike = strike
                best_gamma = gamma
                
        return best_strike, best_gamma
    
    def get_momentum_bias(self) -> str:
        """Get momentum bias"""
        cutoff_time = datetime.now() - timedelta(minutes=3)
        recent_trades = [t for t in self.momentum_tracker if t['timestamp'] > cutoff_time]
        
        if not recent_trades:
            return "NEUTRAL"
            
        above_volume = sum(t['volume'] for t in recent_trades if t['strike'] > self.current_spx_level)
        below_volume = sum(t['volume'] for t in recent_trades if t['strike'] <= self.current_spx_level)
        
        if above_volume > below_volume * 1.3:
            return "UPWARD"
        elif below_volume > above_volume * 1.3:
            return "DOWNWARD"
        else:
            return "NEUTRAL"
    
    def get_static_bias(self) -> str:
        """Get static bias"""
        upward_gamma = sum(abs(data['net_gamma']) for strike, data in self.strikes.items() 
                          if strike > self.current_spx_level and data['total_volume'] >= 5)
        downward_gamma = sum(abs(data['net_gamma']) for strike, data in self.strikes.items() 
                            if strike <= self.current_spx_level and data['total_volume'] >= 5)
        
        if upward_gamma > downward_gamma * 1.2:
            return "UPWARD"
        elif downward_gamma > upward_gamma * 1.2:
            return "DOWNWARD"
        else:
            return "NEUTRAL"
    
    def generate_enhanced_analysis(self, save_to_db: bool = False) -> str:
        """Generate analysis output"""
        confidence_data = self.calculate_enhanced_confidence()
        primary_pin_strike, primary_pin_gamma = self.get_primary_pin_target()
        static_bias = self.get_static_bias()
        momentum_bias = self.get_momentum_bias()
        
        # Get pins
        upward_pins = [(strike, data) for strike, data in self.strikes.items() 
                      if strike > self.current_spx_level and abs(data['net_gamma']) >= 10]
        downward_pins = [(strike, data) for strike, data in self.strikes.items() 
                        if strike <= self.current_spx_level and abs(data['net_gamma']) >= 10]
        
        upward_pins.sort(key=lambda x: abs(x[1]['net_gamma']), reverse=True)
        downward_pins.sort(key=lambda x: abs(x[1]['net_gamma']), reverse=True)
        
        # Confidence emoji
        confidence_emoji = ("🔥" if confidence_data['total'] >= 0.8 else 
                           "💪" if confidence_data['total'] >= 0.65 else 
                           "📊" if confidence_data['total'] >= 0.5 else 
                           "⚠️" if confidence_data['total'] >= 0.35 else "❓")
        
        output = f"""
🎯 ENHANCED PIN & MOMENTUM ANALYSIS - {datetime.now().strftime('%H:%M:%S')}
SPX Level: {self.current_spx_level:.2f}
Trades Processed: {self.total_trades_processed:,}

📊 CONFIDENCE BREAKDOWN:
  Static Pin Strength: {confidence_data['static_pin']:.1%} (gamma concentration)
  Momentum Strength: {confidence_data['momentum']:.1%} (trending activity)
  → TOTAL CONFIDENCE: {confidence_data['total']:.1%} {confidence_emoji}

🎯 STATIC PIN ANALYSIS:
  Primary Target: {primary_pin_strike:.0f} ({primary_pin_gamma:.0f} gamma units)"""
        
        # Add upward pins
        if upward_pins:
            output += "\n📈 UPWARD PINS (Calls Above SPX):"
            for strike, data in upward_pins[:3]:
                marker = " ← STRONGEST" if strike == primary_pin_strike else ""
                output += f"\n  {strike:.0f}: {abs(data['net_gamma']):.0f} gamma units{marker}"
        
        # Add downward pins
        if downward_pins:
            output += "\n📉 DOWNWARD PINS (Puts Below SPX):"
            for strike, data in downward_pins[:3]:
                marker = " ← STRONGEST" if strike == primary_pin_strike else ""
                output += f"\n  {strike:.0f}: {abs(data['net_gamma']):.0f} gamma units{marker}"
        
        # Momentum
        output += "\n\n⚡ MOMENTUM SIGNALS:"
        if len(self.momentum_tracker) >= 10:
            output += "\n  📊 Recent activity detected"
        else:
            output += "\n  💤 Waiting for more data..."
        
        # Bias
        static_emoji = "📈" if static_bias == "UPWARD" else "📉" if static_bias == "DOWNWARD" else "➡️"
        momentum_emoji = "📈" if momentum_bias == "UPWARD" else "📉" if momentum_bias == "DOWNWARD" else "➡️"
        
        if static_bias == momentum_bias == "UPWARD":
            combined_signal = "🚀 STRONG UPWARD"
        elif static_bias == momentum_bias == "DOWNWARD":
            combined_signal = "📉 STRONG DOWNWARD"
        else:
            combined_signal = "⚡ MIXED SIGNALS"
        
        output += f"""

📈 DIRECTIONAL BIAS:
  Static Pin Bias: {static_bias} {static_emoji}
  Dynamic Momentum: {momentum_bias} {momentum_emoji}
  Combined Signal: {combined_signal}
"""
        
        return output

def create_enhanced_pin_detector(db_path: str = "data/enhanced_pins.db") -> EnhancedPinDetector:
    """Create enhanced pin detector"""
    return EnhancedPinDetector(db_path)
