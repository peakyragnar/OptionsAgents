#!/usr/bin/env python3
"""
Test the snapshot system to ensure it works correctly
"""

import sys
import os
from datetime import datetime
import pandas as pd

# Test 1: Check environment
print("=" * 60)
print("SNAPSHOT SYSTEM TEST")
print("=" * 60)

# Check API key
api_key = os.getenv("POLYGON_KEY")
if api_key:
    print("✅ POLYGON_KEY found in environment")
    print(f"   Key starts with: {api_key[:10]}...")
else:
    print("❌ POLYGON_KEY not found!")
    print("   Run: export POLYGON_KEY=your_key_here")
    sys.exit(1)

# Test 2: Import and run snapshot
print("\n📸 Testing snapshot download...")
try:
    from src.ingest.snapshot_fixed import main as snapshot_main
    
    # Run snapshot
    success = snapshot_main()
    
    if success:
        print("✅ Snapshot completed successfully!")
    else:
        print("❌ Snapshot failed - check logs")
        sys.exit(1)
        
except Exception as e:
    print(f"❌ Error running snapshot: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 3: Verify snapshot data
print("\n🔍 Verifying snapshot data...")
try:
    # Find today's snapshots
    today = datetime.now().strftime("%Y-%m-%d")
    snapshot_dir = f"data/parquet/spx/date={today}"
    
    if not os.path.exists(snapshot_dir):
        print(f"❌ No snapshot directory for today: {snapshot_dir}")
        sys.exit(1)
    
    # Get latest file
    files = sorted([f for f in os.listdir(snapshot_dir) if f.endswith('.parquet')])
    if not files:
        print("❌ No snapshot files found")
        sys.exit(1)
    
    latest_file = os.path.join(snapshot_dir, files[-1])
    print(f"📄 Checking file: {latest_file}")
    
    # Load and verify
    df = pd.read_parquet(latest_file)
    
    print(f"\n📊 Snapshot Statistics:")
    print(f"   - Rows: {len(df)}")
    print(f"   - Columns: {df.columns.tolist()}")
    print(f"   - SPX Price: {df['under_px'].iloc[0]:.2f}")
    print(f"   - Expiry: {df['expiry'].iloc[0]}")
    print(f"   - Calls: {len(df[df['type'] == 'C'])}")
    print(f"   - Puts: {len(df[df['type'] == 'P'])}")
    print(f"   - Strike range: {df['strike'].min():.0f} - {df['strike'].max():.0f}")
    
    # Check for today's expiry
    if df['expiry'].iloc[0] == today:
        print("✅ Expiry date is TODAY (0DTE)")
    else:
        print(f"⚠️  Expiry date is {df['expiry'].iloc[0]} (not today)")
    
    # Sample data
    print(f"\n📋 Sample data:")
    print(df[['type', 'strike', 'bid', 'ask', 'iv', 'gamma']].head())
    
except Exception as e:
    print(f"❌ Error verifying snapshot: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Test 4: Test live mode symbol loading
print("\n🚀 Testing live mode symbol loading...")
try:
    from src.cli import load_symbols_from_snapshot
    
    symbols, spx_price = load_symbols_from_snapshot()
    
    if symbols:
        print(f"✅ Loaded {len(symbols)} symbols")
        print(f"   SPX price: {spx_price}")
        print(f"   Sample symbols: {symbols[:5]}")
    else:
        print("❌ No symbols loaded - this is why live mode fails!")
        
except Exception as e:
    print(f"❌ Error loading symbols: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 60)
print("TEST COMPLETE")
print("=" * 60)