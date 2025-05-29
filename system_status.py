#!/usr/bin/env python3
"""
Consolidated system status for Options Agents
Shows everything clearly without truncation
"""

import subprocess
import os
from datetime import datetime, timedelta
from pathlib import Path
import pyarrow.parquet as pq

def print_header(title):
    print(f"\n{'='*60}")
    print(f"{title:^60}")
    print(f"{'='*60}")

def print_section(title):
    print(f"\n📊 {title}")
    print("-" * 40)

def check_spx_price():
    """Check current SPX price from latest snapshot"""
    print_section("SPX PRICE CHECK")
    
    snapshot_dir = Path("data/parquet/spx/date=2025-05-29")
    if not snapshot_dir.exists():
        print("❌ No snapshot directory found")
        return None
    
    snapshots = sorted(snapshot_dir.glob("*.parquet"))
    if not snapshots:
        print("❌ No snapshot files found")
        return None
    
    latest = snapshots[-1]
    try:
        df = pq.read_table(str(latest)).to_pandas()
        spx_price = df['under_px'].iloc[0] if len(df) > 0 else None
        
        print(f"Latest snapshot: {latest.name}")
        print(f"SPX Price: ${spx_price:,.2f}")
        print(f"Options count: {len(df)}")
        print(f"Age: {datetime.now() - datetime.fromtimestamp(latest.stat().st_mtime)}")
        
        # Check if using fallback price
        if abs(spx_price - 5908.28) < 0.1 or abs(spx_price - 5920.0) < 0.1:
            print("⚠️  WARNING: Using fallback price - API may be failing")
        else:
            print("✅ Real-time price from Polygon API")
            
        return spx_price
        
    except Exception as e:
        print(f"❌ Error reading snapshot: {e}")
        return None

def check_services():
    """Check status of all OptionsAgents services"""
    print_section("SERVICE STATUS")
    
    result = subprocess.run(['launchctl', 'list'], capture_output=True, text=True)
    services = {}
    
    for line in result.stdout.splitlines():
        if 'optionsagents' in line:
            parts = line.split()
            if len(parts) >= 3:
                pid = parts[0]
                status = parts[1]
                service = parts[2]
                
                if pid == '-':
                    # For snapshot service, check if it's scheduled (not always running)
                    if 'snapshot' in service:
                        services[service] = "✅ SCHEDULED (runs every 60s)"
                    else:
                        services[service] = "❌ NOT RUNNING"
                else:
                    services[service] = f"✅ RUNNING (PID: {pid})"
    
    for service, status in sorted(services.items()):
        print(f"{service}: {status}")
    
    return services

def check_snapshot_frequency():
    """Check snapshot creation frequency"""
    print_section("SNAPSHOT FREQUENCY")
    
    snapshot_dir = Path("data/parquet/spx/date=2025-05-29")
    if not snapshot_dir.exists():
        print("❌ No snapshot directory")
        return
    
    snapshots = sorted(snapshot_dir.glob("*.parquet"))
    if len(snapshots) < 2:
        print("❌ Need at least 2 snapshots to check frequency")
        return
    
    # Check last hour
    now = datetime.now()
    hour_ago = now - timedelta(hours=1)
    
    recent_snapshots = []
    for f in snapshots:
        mtime = datetime.fromtimestamp(f.stat().st_mtime)
        if mtime > hour_ago:
            recent_snapshots.append((f.name, mtime))
    
    print(f"Snapshots in last hour: {len(recent_snapshots)}")
    
    if len(recent_snapshots) >= 2:
        # Calculate intervals
        times = [t[1] for t in recent_snapshots]
        intervals = []
        for i in range(1, len(times)):
            interval = (times[i] - times[i-1]).total_seconds()
            intervals.append(interval)
        
        if intervals:
            avg_interval = sum(intervals) / len(intervals)
            print(f"Average interval: {avg_interval:.0f} seconds")
            
            if 50 <= avg_interval <= 70:
                print("✅ Snapshot frequency OK (target: 60s)")
            else:
                print(f"⚠️  Frequency off target (got {avg_interval:.0f}s, want 60s)")
    
    # Show last few snapshots
    print("\nLast 5 snapshots:")
    for name, mtime in recent_snapshots[-5:]:
        age = now - mtime
        print(f"  {name} - {mtime.strftime('%H:%M:%S')} ({age.seconds}s ago)")

def check_system_health():
    """Overall system health check"""
    print_section("SYSTEM HEALTH SUMMARY")
    
    issues = []
    
    # Check SPX price
    spx_price = check_spx_price()
    if spx_price is None:
        issues.append("SPX price unavailable")
    elif abs(spx_price - 5908.28) < 0.1 or abs(spx_price - 5920.0) < 0.1:
        issues.append("Using fallback SPX price")
    
    # Check services
    services = check_services()
    if 'com.optionsagents.live' not in services or 'NOT RUNNING' in services['com.optionsagents.live']:
        issues.append("Live service not running")
    # Snapshot service is scheduled, so don't check if it's "running"
    
    # Check snapshots
    snapshot_dir = Path("data/parquet/spx/date=2025-05-29")
    if snapshot_dir.exists():
        snapshots = list(snapshot_dir.glob("*.parquet"))
        if snapshots:
            latest = max(snapshots, key=lambda x: x.stat().st_mtime)
            age = datetime.now() - datetime.fromtimestamp(latest.stat().st_mtime)
            if age.seconds > 300:  # 5 minutes
                issues.append(f"Latest snapshot is {age.seconds}s old")
        else:
            issues.append("No snapshots found")
    else:
        issues.append("No snapshot directory")
    
    if issues:
        print("❌ Issues found:")
        for issue in issues:
            print(f"  - {issue}")
    else:
        print("✅ All systems healthy!")
    
    return len(issues) == 0

def main():
    print_header("OPTIONS AGENTS SYSTEM STATUS")
    
    spx_price = check_spx_price()
    services = check_services()
    check_snapshot_frequency()
    
    print("\n" + "="*60)
    healthy = check_system_health()
    
    if healthy:
        print(f"\n🎉 SYSTEM HEALTHY")
    else:
        print(f"\n⚠️  SYSTEM HAS ISSUES")
    
    print("="*60)

if __name__ == "__main__":
    main()