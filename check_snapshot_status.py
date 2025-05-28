#!/usr/bin/env python3
"""
Real-time snapshot system status checker
Shows you exactly what's happening with your snapshots
"""

import os
import sys
import time
from datetime import datetime, timedelta
import pandas as pd
from pathlib import Path
import pytz

# Colors for terminal output
GREEN = '\033[92m'
RED = '\033[91m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'
BOLD = '\033[1m'

def check_snapshots():
    """Check snapshot system status"""
    print(f"\n{BOLD}📊 SNAPSHOT SYSTEM STATUS CHECK{RESET}")
    print("=" * 60)
    
    # 1. Check for today's snapshots
    today = datetime.now().strftime("%Y-%m-%d")
    snapshot_dir = Path(f"data/parquet/spx/date={today}")
    
    print(f"\n{BOLD}1. Today's Snapshots ({today}):{RESET}")
    
    if not snapshot_dir.exists():
        print(f"{RED}❌ No snapshot directory for today!{RESET}")
        print(f"   Expected: {snapshot_dir}")
        return False
    
    # Get all snapshot files sorted by modification time (newest first)
    files = sorted(snapshot_dir.glob("*.parquet"), key=lambda f: f.stat().st_mtime, reverse=True)
    
    if not files:
        print(f"{RED}❌ No snapshot files found!{RESET}")
        return False
    
    print(f"{GREEN}✅ Found {len(files)} snapshots{RESET}")
    
    # Show latest 5 files (already sorted newest first)
    print(f"\n{BOLD}Latest snapshots:{RESET}")
    for f in files[:5]:
        size_mb = f.stat().st_size / 1024 / 1024
        mtime = datetime.fromtimestamp(f.stat().st_mtime)
        age = datetime.now() - mtime
        age_str = str(age).split('.')[0]  # Remove microseconds
        
        if age.total_seconds() < 300:  # Less than 5 minutes
            status = f"{GREEN}🟢 FRESH{RESET}"
        elif age.total_seconds() < 3600:  # Less than 1 hour
            status = f"{YELLOW}🟡 RECENT{RESET}"
        else:
            status = f"{RED}🔴 STALE{RESET}"
        
        print(f"  {f.name} - {size_mb:.1f}MB - {age_str} ago - {status}")
    
    # 2. Check latest snapshot content
    latest_file = files[0]  # First file is newest due to reverse sort
    print(f"\n{BOLD}2. Latest Snapshot Analysis:{RESET}")
    print(f"File: {latest_file.name}")
    
    try:
        df = pd.read_parquet(latest_file)
        
        # Basic info
        print(f"\n{BOLD}Data Summary:{RESET}")
        print(f"  • Total rows: {len(df)}")
        print(f"  • SPX Price: ${df['under_px'].iloc[0]:,.2f}")
        print(f"  • Expiry: {df['expiry'].iloc[0]}")
        
        # Check if expiry is today (0DTE)
        expiry_date = df['expiry'].iloc[0]
        if expiry_date == today:
            print(f"  • {GREEN}✅ 0DTE Options (expiring today){RESET}")
        else:
            print(f"  • {RED}❌ WARNING: Options expire on {expiry_date} (not today!){RESET}")
        
        # Option breakdown
        calls = len(df[df['type'] == 'C'])
        puts = len(df[df['type'] == 'P'])
        print(f"\n{BOLD}Options Breakdown:{RESET}")
        print(f"  • Calls: {calls}")
        print(f"  • Puts: {puts}")
        print(f"  • Strike range: ${df['strike'].min():,.0f} - ${df['strike'].max():,.0f}")
        
        # Data quality check
        print(f"\n{BOLD}Data Quality:{RESET}")
        
        # Check for valid bids/asks
        valid_quotes = df[(df['bid'] > 0) & (df['ask'] > 0)]
        quote_pct = len(valid_quotes) / len(df) * 100
        if quote_pct > 90:
            print(f"  • {GREEN}✅ Quotes: {quote_pct:.1f}% have valid bid/ask{RESET}")
        else:
            print(f"  • {YELLOW}⚠️  Quotes: Only {quote_pct:.1f}% have valid bid/ask{RESET}")
        
        # Check Greeks
        valid_gamma = df[df['gamma'] > 0]
        gamma_pct = len(valid_gamma) / len(df) * 100
        if gamma_pct > 80:
            print(f"  • {GREEN}✅ Greeks: {gamma_pct:.1f}% have valid gamma{RESET}")
        else:
            print(f"  • {YELLOW}⚠️  Greeks: Only {gamma_pct:.1f}% have valid gamma{RESET}")
        
        # Sample data
        print(f"\n{BOLD}Sample Data (ATM strikes):{RESET}")
        spx_price = df['under_px'].iloc[0]
        atm_strikes = df[
            (df['strike'] >= spx_price - 50) & 
            (df['strike'] <= spx_price + 50)
        ].sort_values('strike')
        
        if len(atm_strikes) > 0:
            print(atm_strikes[['type', 'strike', 'bid', 'ask', 'iv', 'gamma']].head(6).to_string())
        
    except Exception as e:
        print(f"{RED}❌ Error reading snapshot: {e}{RESET}")
        return False
    
    # 3. Check snapshot frequency
    print(f"\n{BOLD}3. Snapshot Frequency:{RESET}")
    
    if len(files) >= 2:
        # Get time between last two snapshots
        time1 = datetime.fromtimestamp(files[-2].stat().st_mtime)
        time2 = datetime.fromtimestamp(files[-1].stat().st_mtime)
        gap = (time2 - time1).total_seconds()
        
        if gap < 120:  # Less than 2 minutes
            print(f"{GREEN}✅ Snapshots running frequently (gap: {gap:.0f}s){RESET}")
        elif gap < 600:  # Less than 10 minutes
            print(f"{YELLOW}⚠️  Snapshots running slowly (gap: {gap:.0f}s){RESET}")
        else:
            print(f"{RED}❌ Large gap between snapshots ({gap/60:.0f} minutes){RESET}")
    
    # 4. Check if live mode would work
    print(f"\n{BOLD}4. Live Mode Compatibility:{RESET}")
    
    # Test symbol loading
    try:
        from src.cli import load_symbols_from_snapshot
        symbols, spx_price = load_symbols_from_snapshot()
        
        if symbols:
            print(f"{GREEN}✅ Symbol loading works: {len(symbols)} symbols loaded{RESET}")
            print(f"   SPX Price: ${spx_price:,.2f}")
            print(f"   Sample: {symbols[0]}")
        else:
            print(f"{RED}❌ No symbols loaded - live mode will fail!{RESET}")
            
    except Exception as e:
        print(f"{RED}❌ Error loading symbols: {e}{RESET}")
    
    return True

def check_processes():
    """Check if snapshot processes are running"""
    print(f"\n{BOLD}5. Running Processes:{RESET}")
    
    import subprocess
    
    # Check for snapshot processes
    try:
        result = subprocess.run(
            ['ps', 'aux'], 
            capture_output=True, 
            text=True
        )
        
        processes = result.stdout
        snapshot_procs = [
            line for line in processes.split('\n') 
            if 'snapshot' in line.lower() and 'python' in line
        ]
        
        if snapshot_procs:
            print(f"{GREEN}✅ Found {len(snapshot_procs)} snapshot process(es):{RESET}")
            for proc in snapshot_procs:
                # Extract just the command part
                parts = proc.split()
                if len(parts) > 10:
                    cmd = ' '.join(parts[10:])[:80]  # First 80 chars of command
                    print(f"   • {cmd}...")
        else:
            print(f"{YELLOW}⚠️  No snapshot processes currently running{RESET}")
            
    except Exception as e:
        print(f"Could not check processes: {e}")

def check_logs():
    """Check recent logs for errors"""
    print(f"\n{BOLD}6. Recent Log Activity:{RESET}")
    
    log_file = Path.home() / "logs" / "OptionsAgents" / "app.log"
    
    if log_file.exists():
        # Get last 20 lines
        with open(log_file, 'r') as f:
            lines = f.readlines()
            recent_lines = lines[-20:]
            
        snapshot_lines = [
            line for line in recent_lines 
            if 'snapshot' in line.lower()
        ]
        
        if snapshot_lines:
            print(f"Recent snapshot log entries:")
            for line in snapshot_lines[-5:]:  # Last 5 snapshot-related
                line = line.strip()
                if 'error' in line.lower() or 'fail' in line.lower():
                    print(f"  {RED}• {line}{RESET}")
                else:
                    print(f"  {GREEN}• {line}{RESET}")
        else:
            print(f"{YELLOW}No recent snapshot activity in logs{RESET}")

def main():
    """Run all checks"""
    try:
        check_snapshots()
        check_processes()
        check_logs()
        
        # Final summary
        print(f"\n{BOLD}{'='*60}{RESET}")
        print(f"{BOLD}SUMMARY:{RESET}")
        
        # Quick health check
        today = datetime.now().strftime("%Y-%m-%d")
        snapshot_dir = Path(f"data/parquet/spx/date={today}")
        
        if snapshot_dir.exists():
            files = list(snapshot_dir.glob("*.parquet"))
            if files:
                latest = max(files, key=lambda f: f.stat().st_mtime)
                age = datetime.now() - datetime.fromtimestamp(latest.stat().st_mtime)
                
                if age.total_seconds() < 300:  # Less than 5 minutes old
                    print(f"{GREEN}✅ SYSTEM HEALTHY - Snapshots are current{RESET}")
                elif age.total_seconds() < 3600:  # Less than 1 hour
                    print(f"{YELLOW}⚠️  SYSTEM OK - Snapshots are recent but not current{RESET}")
                else:
                    print(f"{RED}❌ SYSTEM ISSUE - Snapshots are stale{RESET}")
            else:
                print(f"{RED}❌ SYSTEM DOWN - No snapshots today{RESET}")
        else:
            print(f"{RED}❌ SYSTEM DOWN - No snapshot directory{RESET}")
            
        print(f"{BOLD}{'='*60}{RESET}\n")
        
    except Exception as e:
        print(f"{RED}Error running status check: {e}{RESET}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    # Run once or continuously
    if len(sys.argv) > 1 and sys.argv[1] == "--watch":
        print(f"{BOLD}Watching snapshot status (Ctrl+C to stop)...{RESET}")
        while True:
            os.system('clear')  # Clear screen
            main()
            time.sleep(30)  # Check every 30 seconds
    else:
        main()
        print(f"\n{BLUE}Tip: Run with --watch to monitor continuously{RESET}")
        print(f"{BLUE}     python check_snapshot_status.py --watch{RESET}\n")