#!/usr/bin/env python3
"""Simple system monitor that won't truncate output"""

import subprocess
import os
from datetime import datetime, timedelta
from pathlib import Path

def main():
    print("\n" + "="*60)
    print("OPTIONS AGENTS SYSTEM MONITOR")
    print("="*60)
    
    # Check SPX price
    print("\n📈 SPX PRICE CHECK:")
    print("-" * 40)
    
    # Check latest snapshot
    snapshot_dir = Path("data/parquet/spx/date=2025-05-29")
    if snapshot_dir.exists():
        snapshots = sorted(snapshot_dir.glob("*.parquet"))
        if snapshots:
            latest = snapshots[-1]
            print(f"Latest snapshot: {latest.name}")
            
            # Read SPX price from snapshot
            try:
                import pyarrow.parquet as pq
                df = pq.read_table(str(latest)).to_pandas()
                spx_price = df['under_px'].iloc[0] if len(df) > 0 else "N/A"
                print(f"SPX Price in snapshot: ${spx_price:,.2f}")
                print(f"Options count: {len(df)}")
            except Exception as e:
                print(f"Error reading snapshot: {e}")
    
    # Check services
    print("\n🔧 SERVICE STATUS:")
    print("-" * 40)
    
    result = subprocess.run(['launchctl', 'list'], capture_output=True, text=True)
    for line in result.stdout.splitlines():
        if 'optionsagents' in line:
            parts = line.split()
            if len(parts) >= 3:
                pid = parts[0]
                status = parts[1]
                service = parts[2]
                
                if pid == '-':
                    print(f"❌ {service}: NOT RUNNING")
                else:
                    print(f"✅ {service}: RUNNING (PID: {pid})")
    
    # Check snapshot frequency
    print("\n📊 SNAPSHOT FREQUENCY:")
    print("-" * 40)
    
    if snapshot_dir.exists():
        now = datetime.now()
        hour_ago = now - timedelta(hours=1)
        
        recent_snapshots = []
        for f in snapshots:
            stat = f.stat()
            mtime = datetime.fromtimestamp(stat.st_mtime)
            if mtime > hour_ago:
                recent_snapshots.append((f.name, mtime))
        
        print(f"Snapshots in last hour: {len(recent_snapshots)}")
        if len(recent_snapshots) >= 2:
            # Calculate average interval
            times = [t[1] for t in recent_snapshots]
            intervals = []
            for i in range(1, len(times)):
                interval = (times[i] - times[i-1]).total_seconds()
                intervals.append(interval)
            
            if intervals:
                avg_interval = sum(intervals) / len(intervals)
                print(f"Average interval: {avg_interval:.0f} seconds")
                
                if 110 <= avg_interval <= 130:
                    print("✅ Snapshot frequency OK (target: 120s)")
                else:
                    print(f"⚠️  Snapshot frequency off target (got {avg_interval:.0f}s, want 120s)")
        
        # Show last 5 snapshots
        print("\nLast 5 snapshots:")
        for name, mtime in recent_snapshots[-5:]:
            print(f"  {name} - {mtime.strftime('%H:%M:%S')}")
    
    print("\n" + "="*60)
    print("END OF REPORT")
    print("="*60 + "\n")

if __name__ == "__main__":
    main()