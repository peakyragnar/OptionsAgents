#!/usr/bin/env python3
"""
Emergency fix to create a valid snapshot RIGHT NOW
"""

import os
import sys
from dotenv import load_dotenv

# Force load environment variables
load_dotenv()

# Verify key is loaded
api_key = os.getenv('POLYGON_KEY')
if not api_key:
    print("❌ ERROR: POLYGON_KEY not found in environment!")
    print("Please run: export POLYGON_KEY=your_key_here")
    sys.exit(1)

print(f"✅ API Key loaded: {api_key[:10]}...")

# Now run the fixed snapshot
print("\n🚀 Creating fresh snapshot with correct dates...")
print("-" * 60)

try:
    from src.ingest.snapshot_fixed import main
    success = main()
    
    if success:
        print("\n✅ SUCCESS! Fresh snapshot created.")
        
        # Verify it worked
        import pandas as pd
        import glob
        from datetime import datetime
        
        today = datetime.now().strftime("%Y-%m-%d")
        files = glob.glob(f'data/parquet/spx/date={today}/*.parquet')
        if files:
            latest = max(files)
            df = pd.read_parquet(latest)
            print(f"\n📊 Snapshot verified:")
            print(f"  - File: {latest}")
            print(f"  - Rows: {len(df)}")
            print(f"  - SPX: ${df['under_px'].iloc[0]:,.2f}")
            print(f"  - Expiry: {df['expiry'].iloc[0]} ✅")
            
            if df['expiry'].iloc[0] == today:
                print(f"\n🎉 Options expire TODAY - Live mode will work!")
            else:
                print(f"\n⚠️  Options expire {df['expiry'].iloc[0]}")
    else:
        print("\n❌ Snapshot failed!")
        
except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()
    
    # Try alternative approach
    print("\n🔧 Trying alternative snapshot method...")
    try:
        # Run the original snapshot
        os.system("cd /Users/michael/OptionsAgents && source .venv/bin/activate && python -m src.ingest.snapshot")
    except:
        pass