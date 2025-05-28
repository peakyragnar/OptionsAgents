#!/usr/bin/env python3
"""
Quick fix to get your system running NOW
This will create a valid snapshot for today that the live system can use
"""

import os
import sys
os.environ['POLYGON_KEY'] = os.getenv('POLYGON_KEY', '')  # Ensure env var is set

# Run the fixed snapshot
print("🚀 Running emergency snapshot fix...")
print("-" * 60)

try:
    from src.ingest.snapshot_fixed import main
    
    # Run it
    success = main()
    
    if success:
        print("\n✅ SUCCESS! Snapshot created.")
        print("\nYou can now run:")
        print("  python -m src.cli live")
        print("\nOr test first with:")
        print("  python test_snapshot_system.py")
    else:
        print("\n❌ Snapshot failed. Check the logs above for details.")
        
except Exception as e:
    print(f"\n❌ Error: {e}")
    import traceback
    traceback.print_exc()
    
    print("\n🔧 Troubleshooting:")
    print("1. Check POLYGON_KEY is set: echo $POLYGON_KEY")
    print("2. Check network connection")
    print("3. Check if market is open (9:30 AM - 4:00 PM ET)")
    print("4. Run with debug: python -m src.ingest.snapshot_fixed --debug")