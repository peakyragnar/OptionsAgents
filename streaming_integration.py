#!/usr/bin/env python3
"""
Integration of Pin Detection with Existing Streaming System
"""

import asyncio
import json
from datetime import datetime
from typing import Dict, List
import sys
import os

# Add src to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from src.dealer.pin_detector import ZeroDTEPinDetector, Trade
import pandas as pd
import numpy as np


class StreamingPinIntegration:
    """
    Integration layer between your existing streaming and pin detection
    """
    
    def __init__(self, snapshot_path: str = None):
        self.pin_detector = ZeroDTEPinDetector()
        self.snapshot_path = snapshot_path
        self.last_snapshot_update = None
        self.symbol_to_strike = {}  # Map symbols to strikes for quick lookup
        
    def load_current_snapshot(self):
        """
        Load the latest snapshot to get current symbols and gamma values
        This connects to your existing snapshot system
        """
        try:
            # Find the most recent snapshot file
            import glob
            from pathlib import Path
            
            today = datetime.now().strftime("%Y-%m-%d")
            snapshot_dir = Path("data/parquet/spx") / f"date={today}"
            
            if not snapshot_dir.exists():
                print(f"❌ No snapshot directory found: {snapshot_dir}")
                return False
            
            # Get the latest snapshot file
            pattern = str(snapshot_dir / "*.parquet")
            files = glob.glob(pattern)
            
            if not files:
                print(f"❌ No snapshot files found in {snapshot_dir}")
                return False
            
            latest_file = max(files, key=os.path.getctime)
            print(f"📸 Loading snapshot: {latest_file}")
            
            # Load snapshot data
            df = pd.read_parquet(latest_file)
            
            # Update SPX level (approximate from ATM options)
            atm_options = df[abs(df['strike'] - df['strike'].median()) < 20]
            if len(atm_options) > 0:
                # Estimate SPX from ATM call-put parity
                self.pin_detector.current_spx = atm_options['strike'].median()
                print(f"📊 Updated SPX level: {self.pin_detector.current_spx}")
            
            # Convert to options chain format
            options_chain = []
            self.symbol_to_strike = {}
            
            for _, row in df.iterrows():
                option_data = {
                    'symbol': row['symbol'],
                    'strike': row['strike'],
                    'option_type': row['option_type'],
                    'bid': row.get('bid', 0),
                    'ask': row.get('ask', 0),
                    'gamma': row.get('gamma', 0),
                    'volume': row.get('volume', 0)
                }
                options_chain.append(option_data)
                self.symbol_to_strike[row['symbol']] = row['strike']
            
            # Update pin detector's gamma surface
            self.pin_detector.update_gamma_surface(options_chain)
            
            self.last_snapshot_update = datetime.now()
            print(f"✅ Loaded {len(options_chain)} options, {len(self.symbol_to_strike)} symbols")
            return True
            
        except Exception as e:
            print(f"❌ Error loading snapshot: {e}")
            return False
    
    def process_trade_message(self, trade_data: Dict):
        """
        Process trade message from your streaming system
        
        Expected format from Polygon:
        {
            'ev': 'T',
            'sym': 'SPXW250523C05850000',
            'p': 15.50,
            's': 10,
            't': timestamp,
            ...
        }
        """
        try:
            # Skip if not a trade event
            if trade_data.get('ev') != 'T':
                return
            
            symbol = trade_data.get('sym', '')
            
            # Skip if not SPX options
            if not symbol.startswith('SPXW'):
                return
            
            # Get strike from symbol mapping
            strike = self.symbol_to_strike.get(symbol)
            if not strike:
                print(f"⚠️  Unknown symbol: {symbol}")
                return
            
            # Parse option type from symbol
            option_type = 'C' if 'C' in symbol else 'P'
            
            # Create trade object
            trade = Trade(
                symbol=symbol,
                strike=strike,
                option_type=option_type,
                price=trade_data.get('p', 0),
                size=trade_data.get('s', 0),
                timestamp=datetime.fromtimestamp(trade_data.get('t', 0) / 1000),
                side='SELL',  # Will be determined by pin detector
                is_premium_seller=False  # Will be determined by pin detector
            )
            
            # Get current NBBO (you may need to fetch this from your quote cache)
            nbbo_bid, nbbo_ask = self.get_current_nbbo(symbol)
            
            # Process trade through pin detector
            self.pin_detector.process_trade(trade, nbbo_bid, nbbo_ask)
            
            # Optional: Print significant trades
            if trade.size >= 100:  # Large trades
                print(f"🔄 Large trade: {trade.size} {symbol} @ {trade.price}")
            
        except Exception as e:
            print(f"❌ Error processing trade: {e}")
    
    def get_current_nbbo(self, symbol: str) -> tuple:
        """
        Get current NBBO for symbol
        
        This should connect to your existing quote cache
        For now, we'll estimate based on the symbol
        """
        # TODO: Connect to your actual quote cache
        # For testing, we'll create reasonable bid/ask spreads
        
        strike = self.symbol_to_strike.get(symbol, 0)
        if not strike:
            return 0.05, 0.10
        
        # Estimate option price based on distance from ATM
        distance = abs(strike - self.pin_detector.current_spx)
        
        if distance <= 5:  # ATM
            mid_price = 20.0
        elif distance <= 25:  # Near ATM
            mid_price = 10.0
        else:  # OTM
            mid_price = 2.0
        
        spread = max(0.05, mid_price * 0.05)  # 5% spread
        return mid_price - spread/2, mid_price + spread/2
    
    def get_pin_analysis(self) -> Dict:
        """Get current pin analysis"""
        return self.pin_detector.get_pin_summary()
    
    def print_pin_status(self):
        """Print current pin status to console"""
        summary = self.get_pin_analysis()
        
        print("\n" + "="*60)
        print("🎯 0DTE PIN DETECTION STATUS")
        print("="*60)
        print(f"Time: {summary['timestamp'].strftime('%H:%M:%S')}")
        print(f"SPX Level: {summary['current_spx']:.2f}")
        
        if summary['strongest_pin']['strength'] > 0:
            print(f"Strongest Pin: {summary['strongest_pin']['strike']} "
                  f"(${summary['strongest_pin']['strength']:,.0f} force)")
            print(f"Distance: {summary['strongest_pin']['distance_from_spx']:.1f} points")
        else:
            print("No significant pins detected yet")
        
        print(f"Risk Level: {summary['risk_level']}")
        print(f"Total Short Gamma: ${summary['total_short_gamma']:,.0f}")
        print(f"Active Strikes: {summary['total_active_strikes']}")
        
        if summary['top_pin_strikes']:
            print(f"\nTop Pin Strikes:")
            for i, strike_data in enumerate(summary['top_pin_strikes'][:5], 1):
                print(f"  {i}. {strike_data['strike']}: "
                      f"${strike_data['pin_force']:,.0f} force, "
                      f"{strike_data['call_short']}C/{strike_data['put_short']}P")
        
        if summary['recent_alerts']:
            print(f"\n⚠️  ALERTS:")
            for alert in summary['recent_alerts']:
                print(f"  {alert}")
        
        print("="*60)


async def test_integration():
    """Test the integration with simulated data"""
    
    print("🚀 Testing Pin Detection Integration")
    print("="*50)
    
    # Create integration instance
    integration = StreamingPinIntegration()
    
    # Load current snapshot
    if not integration.load_current_snapshot():
        print("❌ Failed to load snapshot - using test data")
        # Set up test data
        integration.pin_detector.current_spx = 5850.0
        integration.symbol_to_strike = {
            'SPXW250523C05850000': 5850.0,
            'SPXW250523C05860000': 5860.0,
            'SPXW250523P05840000': 5840.0,
        }
    
    # Simulate some trade messages
    test_trades = [
        {
            'ev': 'T',
            'sym': 'SPXW250523C05860000',
            'p': 15.50,
            's': 500,
            't': int(datetime.now().timestamp() * 1000)
        },
        {
            'ev': 'T',
            'sym': 'SPXW250523P05840000', 
            'p': 12.25,
            's': 1000,
            't': int(datetime.now().timestamp() * 1000)
        },
        {
            'ev': 'T',
            'sym': 'SPXW250523C05850000',
            'p': 18.75,
            's': 2000,
            't': int(datetime.now().timestamp() * 1000)
        }
    ]
    
    print(f"\n📊 Processing {len(test_trades)} test trades...")
    
    # Process test trades
    for trade_data in test_trades:
        integration.process_trade_message(trade_data)
        await asyncio.sleep(0.1)  # Small delay between trades
    
    # Show results
    integration.print_pin_status()
    
    return integration


def integrate_with_existing_stream():
    """
    Instructions for integrating with your existing streaming code
    """
    
    print("""
    🔗 INTEGRATION INSTRUCTIONS:
    
    1. Add this to your existing streaming code:
    
    ```python
    from src.dealer.pin_detector import ZeroDTEPinDetector
    from streaming_integration import StreamingPinIntegration
    
    # Initialize pin detection
    pin_integration = StreamingPinIntegration()
    pin_integration.load_current_snapshot()
    
    # In your WebSocket message handler:
    async def handle_message(message):
        data = json.loads(message)
        
        # Your existing code...
        
        # Add pin detection:
        if isinstance(data, list):
            for item in data:
                pin_integration.process_trade_message(item)
        else:
            pin_integration.process_trade_message(data)
        
        # Print status every 100 trades or 5 minutes
        if trade_count % 100 == 0:
            pin_integration.print_pin_status()
    ```
    
    2. Run your streaming with pin detection:
    
    ```bash
    python -m src.cli live
    ```
    
    3. Monitor pin detection in separate terminal:
    
    ```bash
    python streaming_integration.py
    ```
    """)


if __name__ == "__main__":
    # Run test
    asyncio.run(test_integration())
    
    # Show integration instructions
    integrate_with_existing_stream()