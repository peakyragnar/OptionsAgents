#!/usr/bin/env python3
"""
Create snapshot for next trading day (handles after-hours correctly)
"""

import os
import sys
from datetime import datetime, timedelta
import pytz
from dotenv import load_dotenv

# Load environment
load_dotenv()

print("🕐 Checking market status...")

# Get current time in ET
et_tz = pytz.timezone('US/Eastern')
now = datetime.now(et_tz)
print(f"Current ET time: {now.strftime('%Y-%m-%d %H:%M:%S %Z')}")

# Determine which options to fetch
if now.hour >= 16 or now.weekday() >= 5:  # After 4 PM or weekend
    print("📅 Market closed - fetching NEXT trading day options")
    
    # Calculate next trading day
    next_day = now + timedelta(days=1)
    while next_day.weekday() >= 5:  # Skip weekends
        next_day += timedelta(days=1)
    
    target_date = next_day.strftime('%Y-%m-%d')
    print(f"Target expiry: {target_date}")
else:
    print("📅 Market open - fetching TODAY's options")
    target_date = now.strftime('%Y-%m-%d')

# Create a temporary snapshot fetcher for next day
import pandas as pd
from polygon import RESTClient
import time

api_key = os.getenv('POLYGON_KEY')
if not api_key:
    print("❌ No API key!")
    sys.exit(1)

client = RESTClient(api_key)

print(f"\n🔄 Fetching options for {target_date}...")

try:
    # Get SPX price first
    print("Getting SPX price...")
    
    # Try to get last close
    aggs = client.get_aggs(
        ticker="I:SPX",
        multiplier=1,
        timespan="day",
        from_=(datetime.now() - timedelta(days=5)).strftime('%Y-%m-%d'),
        to=datetime.now().strftime('%Y-%m-%d'),
        adjusted=True,
        sort="desc",
        limit=5
    )
    
    spx_price = 5920.0  # Default
    if hasattr(aggs, 'results') and aggs.results:
        spx_price = float(aggs.results[0].close)
    
    print(f"SPX Price: ${spx_price:,.2f}")
    
    # Fetch options
    print(f"Fetching options expiring {target_date}...")
    
    options_data = []
    options_iter = client.list_snapshot_options_chain(
        "SPX",
        params={
            "expiration_date": target_date,
            "strike_price.gte": spx_price * 0.95,
            "strike_price.lte": spx_price * 1.05
        }
    )
    
    count = 0
    for opt in options_iter:
        options_data.append({
            'type': 'C' if opt.details.contract_type == 'call' else 'P',
            'strike': float(opt.details.strike_price),
            'expiry': target_date,
            'bid': getattr(opt.last_quote, 'bid', 0) if hasattr(opt, 'last_quote') else 0,
            'ask': getattr(opt.last_quote, 'ask', 0) if hasattr(opt, 'last_quote') else 0,
            'volume': getattr(opt.day, 'volume', 0) if hasattr(opt, 'day') else 0,
            'open_interest': getattr(opt.day, 'open_interest', 0) if hasattr(opt, 'day') else 0,
            'iv': 0.20,  # Default IV
            'gamma': 0.001,  # Default gamma
            'vega': 1.0,
            'theta': -0.5,
            'delta': 0.5,
            'under_px': spx_price
        })
        
        count += 1
        if count % 100 == 0:
            print(f"  Fetched {count} options...")
            time.sleep(0.1)  # Rate limit
        
        if count >= 500:  # Limit for testing
            break
    
    if options_data:
        # Save snapshot
        df = pd.DataFrame(options_data)
        
        # Create filename with current timestamp
        output_dir = f"data/parquet/spx/date={datetime.now().strftime('%Y-%m-%d')}"
        os.makedirs(output_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime("%H_%M_%S")
        output_file = f"{output_dir}/{timestamp}_nextday.parquet"
        
        df.to_parquet(output_file, compression='zstd')
        
        print(f"\n✅ SUCCESS! Created snapshot with {len(df)} options")
        print(f"📁 Saved to: {output_file}")
        print(f"📅 Options expire: {target_date}")
        
        # Show sample
        print("\nSample data:")
        print(df[['type', 'strike', 'bid', 'ask']].head())
        
        # Now test if live mode would work
        print("\n🧪 Testing symbol generation...")
        from src.cli import load_symbols_from_snapshot
        symbols, spx = load_symbols_from_snapshot()
        
        if symbols:
            print(f"✅ Generated {len(symbols)} symbols successfully!")
            print(f"   Sample: {symbols[0]}")
        else:
            print("❌ Symbol generation failed")
            
    else:
        print("❌ No options data received")
        
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
    
    print("\n💡 Since market is closed, here's what you should do:")
    print("1. Wait until market opens (9:30 AM ET)")
    print("2. Run: python -m src.ingest.snapshot_fixed")
    print("3. Then run: python -m src.cli live")