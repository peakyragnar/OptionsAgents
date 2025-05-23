#!/usr/bin/env python3
"""
Simple test script for 0DTE Pin Detection
Tests the system with your real snapshot data
"""

import sys
import os
from pathlib import Path
import pandas as pd
from datetime import datetime
import asyncio

# Add src to path
sys.path.append(str(Path(__file__).parent))

# Try to import the pin detector
try:
    from src.dealer.pin_detector import ZeroDTEPinDetector, Trade
    print("✅ Pin detector imported successfully")
except ImportError as e:
    print(f"❌ Could not import pin detector: {e}")
    print("Make sure you saved the pin_detector.py file in src/dealer/")
    sys.exit(1)


def test_with_real_snapshots():
    """Test pin detection with your real snapshot data"""
    
    print("🧪 Testing Pin Detection with Real Data")
    print("="*50)
    
    # Initialize pin detector
    detector = ZeroDTEPinDetector()
    
    # Try to load the latest snapshot
    today = datetime.now().strftime("%Y-%m-%d")
    snapshot_dir = Path("data/parquet/spx") / f"date={today}"
    
    print(f"Looking for snapshots in: {snapshot_dir}")
    
    if not snapshot_dir.exists():
        print(f"❌ Snapshot directory not found: {snapshot_dir}")
        return test_with_mock_data()
    
    # Find latest snapshot file
    import glob
    pattern = str(snapshot_dir / "*.parquet")
    files = glob.glob(pattern)
    
    if not files:
        print(f"❌ No snapshot files found")
        return test_with_mock_data()
    
    latest_file = max(files, key=os.path.getctime)
    print(f"📸 Loading: {latest_file}")
    
    try:
        # Load snapshot
        df = pd.read_parquet(latest_file)
        print(f"✅ Loaded {len(df)} options")
        
        # Estimate SPX level
        if 'strike' in df.columns:
            spx_estimate = df['strike'].median()
            detector.current_spx = spx_estimate
            print(f"📊 Estimated SPX: {spx_estimate}")
        
        # Convert to options chain format
        options_chain = []
        for _, row in df.iterrows():
            option_data = {
                'symbol': row.get('symbol', ''),
                'strike': row.get('strike', 0),
                'option_type': row.get('option_type', 'C'),
                'bid': row.get('bid', 0),
                'ask': row.get('ask', 0),
                'gamma': row.get('gamma', 0),
                'volume': row.get('volume', 0)
            }
            options_chain.append(option_data)
        
        # Update gamma surface
        detector.update_gamma_surface(options_chain)
        print(f"✅ Updated gamma surface with {len(options_chain)} options")
        
        # Test with simulated premium selling trades
        return test_with_real_gamma_data(detector, options_chain)
        
    except Exception as e:
        print(f"❌ Error loading snapshot: {e}")
        return test_with_mock_data()


def test_with_real_gamma_data(detector, options_chain):
    """Test with real gamma data from snapshots"""
    
    print(f"\n🎯 Testing Pin Detection with Real Gamma Data")
    print("-" * 50)
    
    # Find ATM and nearby strikes
    spx = detector.current_spx
    atm_options = [opt for opt in options_chain if abs(opt['strike'] - spx) <= 20]
    
    if not atm_options:
        print("❌ No ATM options found")
        return False
    
    print(f"Found {len(atm_options)} near-ATM options")
    
    # Simulate large premium selling trades
    test_trades = []
    
    # Large call selling above SPX (income strategy)
    call_strikes = [opt['strike'] for opt in atm_options 
                   if opt['option_type'] == 'C' and opt['strike'] > spx]
    
    for strike in call_strikes[:3]:  # Top 3 call strikes
        trade = Trade(
            symbol=f"SPXW250523C{strike:08.0f}000",
            strike=strike,
            option_type='C',
            price=15.0,  # Will be adjusted by detector
            size=500 + int(abs(strike - spx) * 10),  # Larger size closer to ATM
            timestamp=datetime.now(),
            side='SELL',
            is_premium_seller=False  # Will be determined
        )
        test_trades.append(trade)
    
    # Large put selling below SPX
    put_strikes = [opt['strike'] for opt in atm_options 
                  if opt['option_type'] == 'P' and opt['strike'] < spx]
    
    for strike in put_strikes[:3]:  # Top 3 put strikes
        trade = Trade(
            symbol=f"SPXW250523P{strike:08.0f}000",
            strike=strike,
            option_type='P',
            price=12.0,
            size=750 + int(abs(spx - strike) * 15),  # Larger size closer to ATM
            timestamp=datetime.now(),
            side='SELL',
            is_premium_seller=False
        )
        test_trades.append(trade)
    
    print(f"🔄 Processing {len(test_trades)} simulated premium selling trades...")
    
    # Process trades
    for trade in test_trades:
        # Simulate NBBO
        spread = max(0.05, trade.price * 0.05)
        nbbo_bid = trade.price - spread/2
        nbbo_ask = trade.price + spread/2
        
        detector.process_trade(trade, nbbo_bid, nbbo_ask)
        print(f"   {trade.size} {trade.option_type} @ {trade.strike}")
    
    # Get analysis
    summary = detector.get_pin_summary()
    
    # Display results
    print(f"\n🎯 PIN DETECTION RESULTS")
    print("="*50)
    print(f"SPX Level: {summary['current_spx']:.2f}")
    
    if summary['strongest_pin']['strength'] > 0:
        print(f"Strongest Pin: {summary['strongest_pin']['strike']} "
              f"(${summary['strongest_pin']['strength']:,.0f} force)")
        print(f"Distance from SPX: {summary['strongest_pin']['distance_from_spx']:.1f} points")
    
    print(f"Risk Level: {summary['risk_level']}")
    print(f"Total Short Gamma: ${summary['total_short_gamma']:,.0f}")
    print(f"Active Strikes: {summary['total_active_strikes']}")
    
    if summary['top_pin_strikes']:
        print(f"\nTop Pin Strikes:")
        for i, strike_data in enumerate(summary['top_pin_strikes'][:5], 1):
            distance = abs(strike_data['strike'] - summary['current_spx'])
            print(f"  {i}. Strike {strike_data['strike']}: "
                  f"${strike_data['pin_force']:,.0f} force "
                  f"({distance:.0f} pts from SPX)")
    
    if summary['recent_alerts']:
        print(f"\n⚠️  Alerts:")
        for alert in summary['recent_alerts']:
            print(f"  {alert}")
    
    return True


def test_with_mock_data():
    """Fallback test with mock data"""
    
    print(f"\n🧪 Testing with Mock Data")
    print("-" * 30)
    
    detector = ZeroDTEPinDetector()
    detector.current_spx = 5850.0
    
    # Create mock gamma surface
    mock_options = []
    for strike in range(5800, 5901, 5):
        for opt_type in ['C', 'P']:
            distance = abs(strike - 5850)
            gamma = max(0.001, 0.01 - distance * 0.0002)  # Higher gamma near ATM
            
            mock_options.append({
                'symbol': f'SPXW250523{opt_type}{strike:08.0f}000',
                'strike': strike,
                'option_type': opt_type,
                'gamma': gamma,
                'bid': 10.0,
                'ask': 11.0
            })
    
    detector.update_gamma_surface(mock_options)
    
    # Test with mock trades
    test_trades = [
        Trade('SPXW250523C05860000', 5860, 'C', 15.0, 1000, datetime.now(), 'SELL', False),
        Trade('SPXW250523P05840000', 5840, 'P', 12.0, 1500, datetime.now(), 'SELL', False),
        Trade('SPXW250523C05855000', 5855, 'C', 18.0, 800, datetime.now(), 'SELL', False),
    ]
    
    for trade in test_trades:
        detector.process_trade(trade, 14.5, 15.5)
    
    summary = detector.get_pin_summary()
    print(f"Mock test completed - found {summary['total_active_strikes']} active strikes")
    
    return True


async def main():
    """Main test function"""
    
    print("🚀 0DTE Pin Detection System Test")
    print("="*60)
    
    # Test 1: Try with real snapshot data
    success = test_with_real_snapshots()
    
    if success:
        print(f"\n✅ Pin detection test completed successfully!")
        print(f"\n🔗 Next steps:")
        print(f"1. Integrate with your streaming: modify src/cli.py")
        print(f"2. Run: python -m src.cli live")
        print(f"3. Monitor pins in real-time")
    else:
        print(f"\n❌ Test failed - check setup")
    
    return success


if __name__ == "__main__":
    asyncio.run(main())