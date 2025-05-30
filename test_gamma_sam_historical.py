#!/usr/bin/env python3
"""
Test Gamma Tool Sam with historical snapshot data
Uses existing parquet files to simulate trades
"""

import asyncio
import duckdb
import pandas as pd
from datetime import datetime
import random
import time

from gamma_tool_sam.gamma_engine import GammaEngine

def load_test_data():
    """Load recent option data from parquet files"""
    conn = duckdb.connect(':memory:')
    
    print("📊 Loading option chain data...")
    
    try:
        # Load only near-the-money options with significant gamma
        df = conn.execute("""
            SELECT 
                strike,
                type,
                bid,
                ask,
                open_interest,
                gamma,
                delta,
                under_px,
                COALESCE(volume, 10) as volume
            FROM read_parquet('data/parquet/spx/date=2025-05-29/*.parquet')
            WHERE gamma IS NOT NULL
            AND gamma > 0.00001  -- Only options with meaningful gamma
            AND bid > 0
            AND ask > 0
            AND strike BETWEEN 5800 AND 6000  -- Near the money only
            ORDER BY gamma DESC
            LIMIT 200  -- Limit to top 200 by gamma
        """).df()
        
        # Create proper symbols for each option
        from datetime import datetime
        today = datetime.now().strftime('%y%m%d')
        
        df['symbol'] = df.apply(
            lambda row: f"O:SPXW{today}{row['type'][0]}{int(row['strike']*1000):08d}", 
            axis=1
        )
        
        print(f"✅ Loaded {len(df)} option records")
        print(f"📊 Strike range: {df['strike'].min():.0f} - {df['strike'].max():.0f}")
        print(f"📍 SPX Price: ${df['under_px'].iloc[0]:,.2f}")
        
        # Show distribution
        strike_counts = df.groupby('strike').size()
        print(f"📈 Strikes with data: {len(strike_counts)}")
        
    except Exception as e:
        print(f"❌ Error loading data: {e}")
        df = pd.DataFrame()
    
    conn.close()
    return df

def simulate_trades(engine, test_data):
    """Simulate trades from historical data"""
    print("\n📊 Simulating trades from historical data...")
    
    if test_data.empty:
        print("❌ No test data available")
        return
        
    # Set SPX price from data
    spx_price = test_data['under_px'].iloc[0]
    engine.gamma_calculator.update_spx_price(spx_price)
    print(f"📍 SPX Price set to: ${spx_price:,.2f}")
    
    # Simulate trades with more variety
    trades_to_simulate = min(200, len(test_data))
    
    # Group by strike to simulate concentrated activity
    strikes = test_data['strike'].unique()
    print(f"📍 Found {len(strikes)} unique strikes")
    
    # Simulate opening surge
    print("\n🔔 Simulating market open...")
    for i in range(min(50, len(test_data))):
        row = test_data.iloc[i]
        
        # Create trade data
        trade_data = {
            'symbol': row['symbol'],
            'price': (row['bid'] + row['ask']) / 2 if row['bid'] > 0 else row['ask'],
            'size': random.randint(10, 100),  # Larger sizes at open
            'timestamp': int(time.time() * 1000),
            'conditions': [],
            'exchange': 'CBOE'
        }
        
        # Process through engine
        engine.trade_processor.process_trade(trade_data)
    
    print(f"✅ Processed {min(50, len(test_data))} opening trades")
    
    # Simulate pin formation at specific strikes (simplified)
    if len(strikes) > 5:
        # Pick 3 strikes near SPX
        spx = engine.gamma_calculator.spx_price
        near_strikes = [s for s in strikes if abs(s - spx) < 30][:3]
        
        if near_strikes:
            print(f"\n📌 Simulating pin formation at strikes: {near_strikes}...")
            
            for strike in near_strikes:
                # Just a few trades per strike to avoid bottleneck
                strike_options = test_data[test_data['strike'] == strike].head(2)
                
                for _, row in strike_options.iterrows():
                    # 2-3 trades per option
                    for j in range(2):
                        trade_data = {
                            'symbol': row['symbol'],
                            'price': (row['bid'] + row['ask']) / 2,
                            'size': random.randint(100, 300),
                            'timestamp': int(time.time() * 1000) + j * 1000,
                            'conditions': [],
                            'exchange': 'CBOE'
                        }
                        engine.trade_processor.process_trade(trade_data)
                        
            print(f"✅ Created pins at {len(near_strikes)} strikes")
    
    # Add some random trades
    remaining = trades_to_simulate - engine.trade_processor.trades_processed
    if remaining > 0:
        print(f"\n📊 Adding {remaining} additional trades...")
        for i in range(remaining):
            row = test_data.iloc[i % len(test_data)]
            trade_data = {
                'symbol': row['symbol'],
                'price': (row['bid'] + row['ask']) / 2 if row['bid'] > 0 else 1.0,
                'size': random.randint(5, 50),
                'timestamp': int(time.time() * 1000) + i * 50,
                'conditions': [],
                'exchange': 'CBOE'
            }
            engine.trade_processor.process_trade(trade_data)
    
    print(f"\n🎯 Simulation complete! Processed {trades_to_simulate} trades")

def main():
    print("""
    ════════════════════════════════════════════
         GAMMA TOOL SAM - TEST MODE
    ════════════════════════════════════════════
    
    Testing with historical snapshot data
    """)
    
    # Load test data
    print("\n📥 Loading historical data...")
    test_data = load_test_data()
    print(f"✅ Loaded {len(test_data)} option records")
    
    if test_data.empty:
        print("❌ No historical data found. Run snapshots first.")
        return
    
    # Initialize engine
    engine = GammaEngine()
    
    # Disable auto-archiving for test speed
    engine.position_tracker.archive_interval = 999999  # Don't archive during test
    
    # Simulate trades
    simulate_trades(engine, test_data)
    
    # Show results
    print("\n" + "="*60)
    print("FINAL ANALYSIS:")
    print("="*60)
    
    # Print dashboard
    engine.print_human_dashboard()
    
    # Show API output
    print("\n🤖 AGENT API OUTPUT:")
    summary = engine.get_pin_summary()
    if summary and 'error' not in summary:
        print(f"Net Force: {summary.get('net_force', 0):+,.0f}")
        print(f"Direction: {summary.get('direction', 'N/A')}")
        print(f"Primary Pin: {summary.get('primary_pin', {})}")
        print(f"Active Alerts: {len(summary.get('active_alerts', []))}")
    
    # Risk assessment
    risk = engine.calculate_risk_level()
    print(f"\n⚠️ Risk Level: {risk['risk_level']} - {risk['reason']}")

if __name__ == "__main__":
    main()