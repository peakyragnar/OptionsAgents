#!/usr/bin/env python3
"""
Complete system monitoring dashboard
Shows real-time status of all OptionsAgents components
"""

import subprocess
import os
import time
from datetime import datetime, timedelta
import pandas as pd
from pathlib import Path

# Colors for terminal output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'
BOLD = '\033[1m'

def check_launchd_services():
    """Check status of launchd services"""
    print(f"\n{BOLD}🚀 LAUNCHD SERVICES{RESET}")
    print("=" * 50)
    
    try:
        result = subprocess.run(['launchctl', 'list'], capture_output=True, text=True)
        services = {}
        
        for line in result.stdout.split('\n'):
            if 'optionsagents' in line:
                parts = line.split('\t')
                if len(parts) >= 3:
                    pid = parts[0]
                    status = parts[1]
                    name = parts[2]
                    services[name] = {'pid': pid, 'status': status}
        
        # Check key services
        key_services = ['com.optionsagents.live', 'com.optionsagents.snapshot']
        
        for service in key_services:
            if service in services:
                pid = services[service]['pid']
                status = services[service]['status']
                
                if pid != '-' and status == '0':
                    print(f"{GREEN}✅ {service:<30} PID: {pid} - RUNNING{RESET}")
                else:
                    print(f"{RED}❌ {service:<30} Status: {status} - FAILED{RESET}")
            else:
                print(f"{RED}❌ {service:<30} NOT LOADED{RESET}")
        
        return services
        
    except Exception as e:
        print(f"{RED}Error checking services: {e}{RESET}")
        return {}

def check_snapshots():
    """Check snapshot creation and freshness"""
    print(f"\n{BOLD}📸 SNAPSHOT STATUS{RESET}")
    print("=" * 50)
    
    today = datetime.now().strftime("%Y-%m-%d")
    snapshot_dir = Path(f"data/parquet/spx/date={today}")
    
    if not snapshot_dir.exists():
        print(f"{RED}❌ No snapshots directory for today{RESET}")
        return False
    
    files = sorted(snapshot_dir.glob("*.parquet"), key=lambda f: f.stat().st_mtime, reverse=True)
    
    if not files:
        print(f"{RED}❌ No snapshot files found{RESET}")
        return False
    
    # Check latest 3 snapshots
    print(f"Latest snapshots:")
    for i, f in enumerate(files[:3]):
        size_mb = f.stat().st_size / 1024 / 1024
        mtime = datetime.fromtimestamp(f.stat().st_mtime)
        age = datetime.now() - mtime
        age_mins = age.total_seconds() / 60
        
        if age_mins < 2:
            status = f"{GREEN}🟢 FRESH{RESET}"
        elif age_mins < 10:
            status = f"{YELLOW}🟡 RECENT{RESET}"
        else:
            status = f"{RED}🔴 STALE{RESET}"
        
        print(f"  {f.name} - {size_mb:.1f}MB - {age_mins:.1f}min ago - {status}")
    
    # Check snapshot content
    try:
        latest = files[0]
        df = pd.read_parquet(latest)
        expiry = df['expiry'].iloc[0]
        
        if expiry == today:
            print(f"{GREEN}✅ Snapshots have correct expiry: {expiry}{RESET}")
        else:
            print(f"{RED}❌ Wrong expiry date: {expiry} (should be {today}){RESET}")
        
        print(f"  Options: {len(df)} | SPX: ${df['under_px'].iloc[0]:,.2f}")
        
    except Exception as e:
        print(f"{RED}❌ Error reading snapshot: {e}{RESET}")
    
    return True

def check_live_trading():
    """Check live trading system status"""
    print(f"\n{BOLD}📊 LIVE TRADING STATUS{RESET}")
    print("=" * 50)
    
    log_file = "/Users/michael/logs/live.out"
    
    if not os.path.exists(log_file):
        print(f"{RED}❌ Live log file not found{RESET}")
        return False
    
    try:
        # Get last 50 lines
        with open(log_file, 'r') as f:
            lines = f.readlines()[-50:]
        
        # Look for key indicators
        recent_lines = ''.join(lines)
        
        # Check for trade processing
        if "Quick Status" in recent_lines:
            print(f"{GREEN}✅ Processing trades (Quick Status found){RESET}")
        elif "📊" in recent_lines:
            print(f"{GREEN}✅ System active (trade symbols found){RESET}")
        else:
            print(f"{YELLOW}⚠️  No recent trade activity{RESET}")
        
        # Check for errors
        error_count = recent_lines.lower().count('error') + recent_lines.lower().count('failed')
        if error_count > 5:
            print(f"{RED}❌ High error count: {error_count} errors in recent logs{RESET}")
        elif error_count > 0:
            print(f"{YELLOW}⚠️  Some errors: {error_count} errors in recent logs{RESET}")
        else:
            print(f"{GREEN}✅ No recent errors{RESET}")
        
        # Check for pin analysis
        if "PIN ANALYSIS" in recent_lines:
            print(f"{GREEN}✅ Pin analysis running{RESET}")
        else:
            print(f"{YELLOW}⚠️  No recent pin analysis{RESET}")
        
        # Show last significant log entry
        significant_lines = [line for line in lines if any(keyword in line for keyword in 
                           ['Quick Status', 'PIN ANALYSIS', '✅', '❌', 'SPX:', 'Confidence'])]
        
        if significant_lines:
            last_line = significant_lines[-1].strip()
            timestamp = last_line.split(' ')[0] if ' ' in last_line else "Unknown"
            print(f"Last activity: {timestamp}")
            print(f"  {last_line[:100]}...")
        
    except Exception as e:
        print(f"{RED}❌ Error reading live logs: {e}{RESET}")
    
    return True

def check_data_flow():
    """Check if data is flowing correctly"""
    print(f"\n{BOLD}🔄 DATA FLOW CHECK{RESET}")
    print("=" * 50)
    
    # Check snapshot frequency
    today = datetime.now().strftime("%Y-%m-%d")
    snapshot_dir = Path(f"data/parquet/spx/date={today}")
    
    if snapshot_dir.exists():
        files = sorted(snapshot_dir.glob("*.parquet"), key=lambda f: f.stat().st_mtime, reverse=True)
        
        if len(files) >= 2:
            # Check time between snapshots
            time1 = datetime.fromtimestamp(files[1].stat().st_mtime)
            time2 = datetime.fromtimestamp(files[0].stat().st_mtime)
            gap = (time2 - time1).total_seconds()
            
            if 50 <= gap <= 70:  # Around 1 minute
                print(f"{GREEN}✅ Snapshot frequency: {gap:.0f}s (target: ~60s){RESET}")
            elif gap < 50:
                print(f"{YELLOW}⚠️  Snapshots too frequent: {gap:.0f}s{RESET}")
            else:
                print(f"{RED}❌ Snapshots too slow: {gap:.0f}s{RESET}")
        
        # Count snapshots in last hour
        one_hour_ago = datetime.now() - timedelta(hours=1)
        recent_files = [f for f in files if datetime.fromtimestamp(f.stat().st_mtime) > one_hour_ago]
        
        print(f"Snapshots in last hour: {len(recent_files)}")
        
        if len(recent_files) >= 50:  # Should be ~60 per hour
            print(f"{GREEN}✅ Good snapshot rate{RESET}")
        elif len(recent_files) >= 30:
            print(f"{YELLOW}⚠️  Reduced snapshot rate{RESET}")
        else:
            print(f"{RED}❌ Low snapshot rate{RESET}")

def check_system_resources():
    """Check system resource usage"""
    print(f"\n{BOLD}💻 SYSTEM RESOURCES{RESET}")
    print("=" * 50)
    
    try:
        # Check CPU usage of Python processes
        result = subprocess.run(['ps', 'aux'], capture_output=True, text=True)
        python_procs = [line for line in result.stdout.split('\n') if 'python' in line and 'OptionsAgents' in line]
        
        total_cpu = 0
        for proc in python_procs:
            parts = proc.split()
            if len(parts) > 2:
                try:
                    cpu = float(parts[2])
                    total_cpu += cpu
                    if cpu > 50:
                        print(f"{RED}⚠️  High CPU process: {cpu}%{RESET}")
                except:
                    pass
        
        if total_cpu < 10:
            print(f"{GREEN}✅ CPU usage: {total_cpu:.1f}%{RESET}")
        elif total_cpu < 25:
            print(f"{YELLOW}⚠️  CPU usage: {total_cpu:.1f}%{RESET}")
        else:
            print(f"{RED}❌ High CPU usage: {total_cpu:.1f}%{RESET}")
        
    except Exception as e:
        print(f"Could not check CPU: {e}")

def main():
    """Run complete system check"""
    print(f"\n{BOLD}{'='*60}{RESET}")
    print(f"{BOLD}🎯 OPTIONSAGENTS SYSTEM MONITOR{RESET}")
    print(f"{BOLD}{'='*60}{RESET}")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Run all checks
    services = check_launchd_services()
    check_snapshots()
    check_live_trading()
    check_data_flow()
    check_system_resources()
    
    # Overall health summary
    print(f"\n{BOLD}📋 SYSTEM HEALTH SUMMARY{RESET}")
    print("=" * 50)
    
    # Quick health indicators
    health_score = 0
    
    # Check if key services are running
    if 'com.optionsagents.live' in services and services['com.optionsagents.live']['pid'] != '-':
        health_score += 30
        print(f"{GREEN}✅ Live trading service running{RESET}")
    else:
        print(f"{RED}❌ Live trading service down{RESET}")
    
    if 'com.optionsagents.snapshot' in services:
        health_score += 20
        print(f"{GREEN}✅ Snapshot service configured{RESET}")
    else:
        print(f"{RED}❌ Snapshot service not configured{RESET}")
    
    # Check snapshot freshness
    today = datetime.now().strftime("%Y-%m-%d")
    snapshot_dir = Path(f"data/parquet/spx/date={today}")
    if snapshot_dir.exists():
        files = list(snapshot_dir.glob("*.parquet"))
        if files:
            latest = max(files, key=lambda f: f.stat().st_mtime)
            age = datetime.now() - datetime.fromtimestamp(latest.stat().st_mtime)
            if age.total_seconds() < 300:  # Less than 5 minutes
                health_score += 30
                print(f"{GREEN}✅ Fresh snapshots available{RESET}")
            else:
                print(f"{YELLOW}⚠️  Snapshots are stale{RESET}")
        else:
            print(f"{RED}❌ No snapshots found{RESET}")
    
    # Overall score
    if health_score >= 70:
        print(f"\n{GREEN}🎉 SYSTEM HEALTHY ({health_score}/80){RESET}")
    elif health_score >= 50:
        print(f"\n{YELLOW}⚠️  SYSTEM NEEDS ATTENTION ({health_score}/80){RESET}")
    else:
        print(f"\n{RED}❌ SYSTEM ISSUES ({health_score}/80){RESET}")
    
    print(f"\n{BOLD}{'='*60}{RESET}")

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1 and sys.argv[1] == "--watch":
        print(f"{BOLD}Monitoring system continuously (Ctrl+C to stop)...{RESET}")
        while True:
            try:
                os.system('clear')
                main()
                time.sleep(30)  # Update every 30 seconds
            except KeyboardInterrupt:
                print(f"\n{BOLD}Monitoring stopped.{RESET}")
                break
    else:
        main()
        print(f"\n{BLUE}💡 Tip: Run with --watch for continuous monitoring{RESET}")
        print(f"{BLUE}    python monitor_system.py --watch{RESET}")