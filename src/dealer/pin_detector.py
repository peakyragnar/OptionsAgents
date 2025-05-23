#!/usr/bin/env python3
"""
0DTE Pin Detection System
Real-time gamma positioning analysis for premium sellers
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
import duckdb
from collections import defaultdict, deque
import asyncio


@dataclass
class Trade:
    """Individual SPX options trade"""
    symbol: str
    strike: float
    option_type: str  # 'C' or 'P'
    price: float
    size: int
    timestamp: datetime
    side: str  # 'BUY' or 'SELL' (customer perspective)
    is_premium_seller: bool  # Key classification


@dataclass
class StrikeGamma:
    """Gamma exposure data for a single strike"""
    strike: float
    call_gamma: float
    put_gamma: float
    spx_distance: float  # Distance from current SPX level


@dataclass
class PinAnalysis:
    """Pin detection results"""
    strongest_pin_strike: float
    pin_strength: float
    total_short_gamma: float
    risk_level: str  # 'LOW', 'MEDIUM', 'HIGH'
    spike_alerts: List[str]


class ZeroDTEPinDetector:
    """
    Real-time 0DTE pin detection system
    Tracks premium sellers' gamma exposure to predict SPX pinning
    """
    
    def __init__(self, db_path: str = "data/intraday.db"):
        self.db_path = db_path
        
        # Cumulative position tracking
        self.cumulative_positions = defaultdict(lambda: {
            'call_short_volume': 0,
            'put_short_volume': 0,
            'call_gamma_exposure': 0.0,
            'put_gamma_exposure': 0.0,
            'total_pin_force': 0.0,
            'last_update': None
        })
        
        # Spike detection (last 5 minutes)
        self.recent_activity = defaultdict(lambda: deque(maxlen=300))  # 5min @ 1sec resolution
        
        # Current market state
        self.current_spx = 5850.0  # Will be updated from market data
        self.current_gamma_surface = {}  # Strike -> StrikeGamma
        
        # Alert thresholds
        self.SPIKE_THRESHOLD = 1000  # Contracts in short time
        self.HIGH_GAMMA_THRESHOLD = 100000  # Dollar gamma exposure
        self.PIN_STRENGTH_THRESHOLD = 500000  # Combined pin force
        
    def classify_premium_seller(self, trade: Trade, nbbo_bid: float, nbbo_ask: float) -> bool:
        """
        Classify if trade represents premium selling
        
        Key insight: Premium sellers typically sell at/near bid
        Premium buyers typically buy at/near ask
        """
        mid_price = (nbbo_bid + nbbo_ask) / 2
        
        # For calls above SPX (likely short calls for income)
        if trade.option_type == 'C' and trade.strike > self.current_spx:
            # Selling call premium - trade near bid
            return trade.price <= mid_price and trade.side == 'SELL'
        
        # For puts below SPX (likely short puts for income)  
        elif trade.option_type == 'P' and trade.strike < self.current_spx:
            # Selling put premium - trade near bid
            return trade.price <= mid_price and trade.side == 'SELL'
        
        # ATM straddles/strangles (premium selling strategies)
        elif abs(trade.strike - self.current_spx) <= 10:
            # Near ATM - look for large size premium selling
            return (trade.side == 'SELL' and 
                   trade.size >= 50 and  # Large size
                   trade.price <= mid_price + 0.05)  # Near/below mid
        
        return False
    
    def update_gamma_surface(self, options_chain: List[Dict]):
        """Update current gamma values for all strikes"""
        self.current_gamma_surface = {}
        
        for option in options_chain:
            strike = option['strike']
            if strike not in self.current_gamma_surface:
                self.current_gamma_surface[strike] = StrikeGamma(
                    strike=strike,
                    call_gamma=0.0,
                    put_gamma=0.0,
                    spx_distance=abs(strike - self.current_spx)
                )
            
            if option['option_type'] == 'C':
                self.current_gamma_surface[strike].call_gamma = option.get('gamma', 0.0)
            else:
                self.current_gamma_surface[strike].put_gamma = option.get('gamma', 0.0)
    
    def process_trade(self, trade: Trade, nbbo_bid: float, nbbo_ask: float):
        """
        Process individual trade for pin detection
        
        Updates both cumulative positions and spike detection
        """
        # Classify if this represents premium selling
        is_premium_seller = self.classify_premium_seller(trade, nbbo_bid, nbbo_ask)
        trade.is_premium_seller = is_premium_seller
        
        if not is_premium_seller:
            return  # Only track premium sellers
        
        strike = trade.strike
        now = datetime.now()
        
        # Update cumulative positions
        pos = self.cumulative_positions[strike]
        
        if trade.option_type == 'C':
            pos['call_short_volume'] += trade.size
            
            # Calculate gamma exposure (negative because short)
            if strike in self.current_gamma_surface:
                gamma = self.current_gamma_surface[strike].call_gamma
                gamma_exposure = -trade.size * gamma * 100  # 100 shares per contract
                pos['call_gamma_exposure'] += gamma_exposure
        
        else:  # Put
            pos['put_short_volume'] += trade.size
            
            if strike in self.current_gamma_surface:
                gamma = self.current_gamma_surface[strike].put_gamma  
                gamma_exposure = -trade.size * gamma * 100
                pos['put_gamma_exposure'] += gamma_exposure
        
        # Update total pin force for this strike
        pos['total_pin_force'] = abs(pos['call_gamma_exposure'] + pos['put_gamma_exposure'])
        pos['last_update'] = now
        
        # Track for spike detection
        self.recent_activity[strike].append({
            'timestamp': now,
            'size': trade.size,
            'option_type': trade.option_type,
            'gamma_impact': abs(gamma_exposure) if 'gamma_exposure' in locals() else 0
        })
        
        # Store to database for backtesting
        self.store_pin_data(trade, pos, now)
    
    def detect_spikes(self, lookback_minutes: int = 5) -> List[str]:
        """
        Detect sudden volume spikes that might indicate large position changes
        """
        alerts = []
        cutoff_time = datetime.now() - timedelta(minutes=lookback_minutes)
        
        for strike, activity in self.recent_activity.items():
            if not activity:
                continue
            
            # Sum recent activity
            recent_volume = 0
            recent_gamma_impact = 0
            
            for event in activity:
                if event['timestamp'] > cutoff_time:
                    recent_volume += event['size']
                    recent_gamma_impact += event['gamma_impact']
            
            # Check for spikes
            if recent_volume > self.SPIKE_THRESHOLD:
                alerts.append(f"VOLUME SPIKE: {recent_volume:,} contracts at {strike} "
                            f"(last {lookback_minutes}min)")
            
            if recent_gamma_impact > self.HIGH_GAMMA_THRESHOLD:
                alerts.append(f"GAMMA SPIKE: ${recent_gamma_impact:,.0f} exposure at {strike} "
                            f"(last {lookback_minutes}min)")
        
        return alerts
    
    def calculate_pin_analysis(self) -> PinAnalysis:
        """
        Calculate current pin detection analysis
        
        Returns comprehensive pin strength and risk assessment
        """
        if not self.cumulative_positions:
            return PinAnalysis(0, 0, 0, 'LOW', [])
        
        # Find strike with strongest pin force
        strongest_strike = 0
        max_pin_force = 0
        total_short_gamma = 0
        
        pin_forces = []
        
        for strike, pos in self.cumulative_positions.items():
            pin_force = pos['total_pin_force']
            total_short_gamma += abs(pos['call_gamma_exposure'] + pos['put_gamma_exposure'])
            
            pin_forces.append((strike, pin_force))
            
            if pin_force > max_pin_force:
                max_pin_force = pin_force
                strongest_strike = strike
        
        # Sort by pin force
        pin_forces.sort(key=lambda x: x[1], reverse=True)
        
        # Determine risk level
        if max_pin_force > self.PIN_STRENGTH_THRESHOLD * 2:
            risk_level = 'HIGH'
        elif max_pin_force > self.PIN_STRENGTH_THRESHOLD:
            risk_level = 'MEDIUM'
        else:
            risk_level = 'LOW'
        
        # Get spike alerts
        spike_alerts = self.detect_spikes()
        
        return PinAnalysis(
            strongest_pin_strike=strongest_strike,
            pin_strength=max_pin_force,
            total_short_gamma=total_short_gamma,
            risk_level=risk_level,
            spike_alerts=spike_alerts
        )
    
    def get_top_pin_strikes(self, n: int = 10) -> List[Tuple[float, float, Dict]]:
        """Get top N strikes by pin force"""
        pin_data = []
        
        for strike, pos in self.cumulative_positions.items():
            pin_force = pos['total_pin_force']
            distance = abs(strike - self.current_spx)
            
            pin_data.append((strike, pin_force, distance, pos))
        
        # Sort by pin force, then by distance from SPX
        pin_data.sort(key=lambda x: (x[1], -x[2]), reverse=True)
        
        return [(strike, pin_force, pos) for strike, pin_force, distance, pos in pin_data[:n]]
    
    def store_pin_data(self, trade: Trade, position_data: Dict, timestamp: datetime):
        """Store pin detection data for backtesting"""
        try:
            with duckdb.connect(self.db_path) as conn:
                # Create table if it doesn't exist
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS pin_analysis (
                        timestamp TIMESTAMP,
                        strike DOUBLE,
                        option_type VARCHAR,
                        trade_size INTEGER,
                        cumulative_call_short INTEGER,
                        cumulative_put_short INTEGER,
                        call_gamma_exposure DOUBLE,
                        put_gamma_exposure DOUBLE,
                        total_pin_force DOUBLE,
                        spx_level DOUBLE,
                        distance_from_atm DOUBLE
                    )
                """)
                
                # Insert current data
                conn.execute("""
                    INSERT INTO pin_analysis VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, [
                    timestamp,
                    trade.strike,
                    trade.option_type,
                    trade.size,
                    position_data['call_short_volume'],
                    position_data['put_short_volume'], 
                    position_data['call_gamma_exposure'],
                    position_data['put_gamma_exposure'],
                    position_data['total_pin_force'],
                    self.current_spx,
                    abs(trade.strike - self.current_spx)
                ])
                
        except Exception as e:
            print(f"Error storing pin data: {e}")
    
    def get_pin_summary(self) -> Dict:
        """Get comprehensive pin detection summary"""
        analysis = self.calculate_pin_analysis()
        top_strikes = self.get_top_pin_strikes(5)
        
        return {
            'timestamp': datetime.now(),
            'current_spx': self.current_spx,
            'strongest_pin': {
                'strike': analysis.strongest_pin_strike,
                'strength': analysis.pin_strength,
                'distance_from_spx': abs(analysis.strongest_pin_strike - self.current_spx)
            },
            'total_short_gamma': analysis.total_short_gamma,
            'risk_level': analysis.risk_level,
            'top_pin_strikes': [
                {
                    'strike': strike,
                    'pin_force': pin_force,
                    'call_short': pos['call_short_volume'],
                    'put_short': pos['put_short_volume'],
                    'total_gamma_exposure': pos['call_gamma_exposure'] + pos['put_gamma_exposure']
                }
                for strike, pin_force, pos in top_strikes
            ],
            'recent_alerts': analysis.spike_alerts,
            'total_active_strikes': len(self.cumulative_positions)
        }
    
    def reset_daily_positions(self):
        """Reset positions for new trading day"""
        self.cumulative_positions.clear()
        self.recent_activity.clear()
        print(f"🔄 Reset 0DTE positions for new trading day")


# ==================== USAGE EXAMPLE ====================

async def run_pin_detection_example():
    """Example of how to use the pin detector"""
    
    detector = ZeroDTEPinDetector()
    
    # Update SPX level and gamma surface (from your snapshot data)
    detector.current_spx = 5852.0
    
    # Mock some trades to demonstrate
    trades = [
        Trade('SPXW250523C05860000', 5860, 'C', 15.50, 100, datetime.now(), 'SELL', False),
        Trade('SPXW250523P05840000', 5840, 'P', 12.25, 250, datetime.now(), 'SELL', False),
        Trade('SPXW250523C05855000', 5855, 'C', 18.75, 500, datetime.now(), 'SELL', False),
    ]
    
    # Process trades
    for trade in trades:
        detector.process_trade(trade, trade.price - 0.25, trade.price + 0.25)
    
    # Get analysis
    summary = detector.get_pin_summary()
    
    print("🎯 0DTE PIN DETECTION SUMMARY")
    print("=" * 50)
    print(f"SPX Level: {summary['current_spx']}")
    print(f"Strongest Pin: {summary['strongest_pin']['strike']} "
          f"(${summary['strongest_pin']['strength']:,.0f} force)")
    print(f"Risk Level: {summary['risk_level']}")
    print(f"Total Short Gamma: ${summary['total_short_gamma']:,.0f}")
    
    print(f"\nTop Pin Strikes:")
    for strike_data in summary['top_pin_strikes'][:3]:
        print(f"  {strike_data['strike']}: "
              f"${strike_data['pin_force']:,.0f} force, "
              f"{strike_data['call_short']}C/{strike_data['put_short']}P short")
    
    if summary['recent_alerts']:
        print(f"\n⚠️  Recent Alerts:")
        for alert in summary['recent_alerts']:
            print(f"  {alert}")


if __name__ == "__main__":
    asyncio.run(run_pin_detection_example())