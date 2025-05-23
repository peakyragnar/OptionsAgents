#!/usr/bin/env python3
"""
OptionsAgents Live Monitoring Dashboard
Real-time validation of data flows and dealer gamma calculations
"""

import time
import asyncio
from datetime import datetime, timedelta
from pathlib import Path
import pandas as pd
import duckdb
import json
from typing import Dict, List, Optional, Tuple
import subprocess
import psutil
import numpy as np
from dataclasses import dataclass
import glob
import os


@dataclass
class SystemHealth:
    """System health metrics"""
    launchd_running: bool
    last_snapshot_time: Optional[datetime]
    last_trade_time: Optional[datetime]
    trade_count_last_minute: int
    unique_strikes_trading: int
    total_dealer_gamma: float
    data_latency_seconds: float
    disk_usage_mb: float


class OptionsAgentsMonitor:
    """Real-time monitoring for OptionsAgents system"""
    
    def __init__(self, data_dir: str = "data", db_path: str = None):
        self.data_dir = Path(data_dir)
        self.parquet_dir = self.data_dir / "parquet" / "spx"
        self.db_path = db_path or os.getenv("OA_GAMMA_DB", "data/intraday.db")
        
        # Create directories if they don't exist
        self.parquet_dir.mkdir(parents=True, exist_ok=True)
        
    def check_launchd_process(self) -> bool:
        """Check if your OptionsAgents launchd process is running"""
        try:
            # Look for python processes running OptionsAgents
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    if proc.info['name'] == 'python' and proc.info['cmdline']:
                        cmdline = ' '.join(proc.info['cmdline'])
                        if 'src.cli' in cmdline or 'OptionsAgents' in cmdline:
                            return True
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
            return False
        except Exception as e:
            print(f"Error checking processes: {e}")
            return False
    
    def get_latest_snapshot_info(self) -> Tuple[Optional[datetime], int]:
        """Get info about the latest snapshot"""
        try:
            # Look for today's snapshots
            today = datetime.now().strftime("%Y-%m-%d")
            today_dir = self.parquet_dir / f"date={today}"
            
            if not today_dir.exists():
                return None, 0
            
            # Find all parquet files for today
            parquet_files = list(today_dir.glob("*.parquet"))
            
            if not parquet_files:
                return None, 0
            
            # Get the most recent file
            latest_file = max(parquet_files, key=lambda f: f.stat().st_mtime)
            latest_time = datetime.fromtimestamp(latest_file.stat().st_mtime)
            
            # Count options in latest snapshot
            try:
                df = pd.read_parquet(latest_file)
                option_count = len(df)
            except Exception as e:
                print(f"Error reading parquet: {e}")
                option_count = 0
            
            return latest_time, option_count
            
        except Exception as e:
            print(f"Error checking snapshots: {e}")
            return None, 0
    
    def get_streaming_trade_info(self) -> Tuple[Optional[datetime], int, int, float]:
        """Get info about streaming trades from DuckDB"""
        try:
            if not Path(self.db_path).exists():
                return None, 0, 0, 0.0
            
            with duckdb.connect(self.db_path) as conn:
                # Check if gamma_snapshots table exists
                tables = conn.execute("SHOW TABLES").fetchall()
                if not any("gamma_snapshots" in str(table) for table in tables):
                    return None, 0, 0, 0.0
                
                # Get latest trade time
                latest_trade = conn.execute("""
                    SELECT MAX(timestamp) as latest_time 
                    FROM gamma_snapshots
                """).fetchone()
                
                latest_time = latest_trade[0] if latest_trade[0] else None
                
                # Get trades in last minute
                one_minute_ago = datetime.now() - timedelta(minutes=1)
                recent_trades = conn.execute("""
                    SELECT COUNT(*) as trade_count
                    FROM gamma_snapshots 
                    WHERE timestamp > ?
                """, [one_minute_ago]).fetchone()
                
                trade_count = recent_trades[0] if recent_trades else 0
                
                # Get unique strikes trading
                unique_strikes = conn.execute("""
                    SELECT COUNT(DISTINCT strike) as strike_count
                    FROM gamma_snapshots 
                    WHERE timestamp > ?
                """, [one_minute_ago]).fetchone()
                
                strike_count = unique_strikes[0] if unique_strikes else 0
                
                # Get total dealer gamma exposure
                total_gamma = conn.execute("""
                    SELECT SUM(dealer_gamma_exposure) as total_gamma
                    FROM gamma_snapshots 
                    WHERE timestamp > ?
                """, [one_minute_ago]).fetchone()
                
                gamma_exposure = total_gamma[0] if total_gamma[0] else 0.0
                
                return latest_time, trade_count, strike_count, gamma_exposure
                
        except Exception as e:
            print(f"Error checking streaming data: {e}")
            return None, 0, 0, 0.0
    
    def get_system_health(self) -> SystemHealth:
        """Get overall system health metrics"""
        
        # Check launchd process
        launchd_running = self.check_launchd_process()
        
        # Check snapshot data
        last_snapshot_time, _ = self.get_latest_snapshot_info()
        
        # Check streaming data
        last_trade_time, trade_count, strike_count, total_gamma = self.get_streaming_trade_info()
        
        # Calculate data latency
        data_latency = float('inf')
        if last_trade_time:
            data_latency = (datetime.now() - last_trade_time).total_seconds()
        
        # Check disk usage
        disk_usage = 0.0
        try:
            if self.data_dir.exists():
                disk_usage = sum(f.stat().st_size for f in self.data_dir.rglob('*') if f.is_file()) / (1024 * 1024)
        except Exception:
            pass
        
        return SystemHealth(
            launchd_running=launchd_running,
            last_snapshot_time=last_snapshot_time,
            last_trade_time=last_trade_time,
            trade_count_last_minute=trade_count,
            unique_strikes_trading=strike_count,
            total_dealer_gamma=total_gamma,
            data_latency_seconds=data_latency,
            disk_usage_mb=disk_usage
        )
    
    def display_dashboard(self):
        """Display real-time dashboard"""
        
        health = self.get_system_health()
        now = datetime.now()
        
        print("\n" + "="*70)
        print(f"🚀 OptionsAgents Live Dashboard - {now.strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*70)
        
        # System Status
        status_emoji = "✅" if health.launchd_running else "❌"
        print(f"\n📊 SYSTEM STATUS: {status_emoji}")
        print(f"   Launch Process: {'RUNNING' if health.launchd_running else 'NOT RUNNING'}")
        
        # Snapshot Data Flow
        print(f"\n📸 SNAPSHOT FLOW (Every 60 seconds):")
        if health.last_snapshot_time:
            time_diff = (now - health.last_snapshot_time).total_seconds()
            freshness = "🟢 FRESH" if time_diff < 120 else "🟡 STALE" if time_diff < 300 else "🔴 OLD"
            print(f"   Last Snapshot: {health.last_snapshot_time.strftime('%H:%M:%S')} ({time_diff:.0f}s ago) {freshness}")
        else:
            print(f"   Last Snapshot: ❌ NO DATA FOUND")
        
        # Streaming Data Flow
        print(f"\n⚡ STREAMING FLOW (Real-time trades):")
        if health.last_trade_time:
            latency_status = "🟢 LIVE" if health.data_latency_seconds < 30 else "🟡 DELAYED" if health.data_latency_seconds < 120 else "🔴 STALE"
            print(f"   Last Trade: {health.last_trade_time.strftime('%H:%M:%S')} ({health.data_latency_seconds:.0f}s ago) {latency_status}")
        else:
            print(f"   Last Trade: ❌ NO TRADES FOUND")
        
        print(f"   Trades/min: {health.trade_count_last_minute}")
        print(f"   Active Strikes: {health.unique_strikes_trading}")
        
        # Dealer Gamma Exposure
        print(f"\n🎯 DEALER GAMMA EXPOSURE:")
        if health.total_dealer_gamma != 0:
            gamma_formatted = f"${health.total_dealer_gamma:,.0f}"
            gamma_direction = "SHORT" if health.total_dealer_gamma < 0 else "LONG"
            print(f"   Total Exposure: {gamma_formatted} ({gamma_direction} GAMMA)")
        else:
            print(f"   Total Exposure: $0 (BALANCED)")
        
        # Data Storage
        print(f"\n💾 DATA STORAGE:")
        print(f"   Disk Usage: {health.disk_usage_mb:.1f} MB")
        print(f"   Database: {self.db_path}")
        
        # Market Hours Check
        market_open = self.is_market_open()
        market_status = "🟢 OPEN" if market_open else "🔴 CLOSED"
        print(f"\n📈 MARKET STATUS: {market_status}")
        
        # Health Summary
        print(f"\n🏥 OVERALL HEALTH:")
        issues = []
        if not health.launchd_running:
            issues.append("Launch process not running")
        if not health.last_snapshot_time or (now - health.last_snapshot_time).total_seconds() > 300:
            issues.append("Snapshot data stale")
        if market_open and (not health.last_trade_time or health.data_latency_seconds > 120):
            issues.append("Trade data stale")
        
        if not issues:
            print("   ✅ ALL SYSTEMS OPERATIONAL")
        else:
            print("   ⚠️  ISSUES DETECTED:")
            for issue in issues:
                print(f"      - {issue}")
        
        print("="*70)
    
    def is_market_open(self) -> bool:
        """Check if US market is currently open"""
        now = datetime.now()
        
        # Check if it's a weekday
        if now.weekday() >= 5:  # Saturday=5, Sunday=6
            return False
        
        # Check market hours (9:30 AM - 4:00 PM ET)
        # This is a simplified check - doesn't account for holidays
        market_open_time = now.replace(hour=9, minute=30, second=0)
        market_close_time = now.replace(hour=16, minute=0, second=0)
        
        return market_open_time <= now <= market_close_time
    
    def detailed_gamma_analysis(self):
        """Show detailed gamma exposure by strike"""
        try:
            if not Path(self.db_path).exists():
                print("❌ No database found")
                return
            
            with duckdb.connect(self.db_path) as conn:
                # Get recent gamma exposure by strike
                recent_data = conn.execute("""
                    SELECT 
                        strike,
                        option_type,
                        SUM(dealer_gamma_exposure) as total_gamma,
                        SUM(customer_buys) as total_buys,
                        SUM(customer_sells) as total_sells,
                        COUNT(*) as trade_count
                    FROM gamma_snapshots 
                    WHERE timestamp > ?
                    GROUP BY strike, option_type
                    ORDER BY ABS(SUM(dealer_gamma_exposure)) DESC
                    LIMIT 15
                """, [datetime.now() - timedelta(minutes=5)]).fetchall()
                
                if not recent_data:
                    print("❌ No recent gamma data found")
                    return
                
                print(f"\n🎯 TOP GAMMA EXPOSURES (Last 5 minutes):")
                print("-" * 80)
                print(f"{'Strike':<8} {'Type':<4} {'Gamma Exp':<12} {'Cust Buys':<10} {'Cust Sells':<11} {'Trades':<7}")
                print("-" * 80)
                
                for row in recent_data:
                    strike, opt_type, gamma, buys, sells, trades = row
                    gamma_str = f"${gamma:,.0f}" if gamma else "$0"
                    print(f"{strike:<8} {opt_type:<4} {gamma_str:<12} {buys:<10} {sells:<11} {trades:<7}")
                
        except Exception as e:
            print(f"Error in gamma analysis: {e}")
    
    async def continuous_monitor(self, refresh_seconds: int = 10):
        """Run continuous monitoring"""
        try:
            while True:
                # Clear screen
                os.system('clear' if os.name == 'posix' else 'cls')
                
                # Display dashboard
                self.display_dashboard()
                
                # Show detailed gamma analysis
                self.detailed_gamma_analysis()
                
                print(f"\n🔄 Refreshing in {refresh_seconds} seconds... (Ctrl+C to exit)")
                
                await asyncio.sleep(refresh_seconds)
                
        except KeyboardInterrupt:
            print("\n\n👋 Monitoring stopped by user")
        except Exception as e:
            print(f"\n❌ Error in continuous monitoring: {e}")


def main():
    """Main monitoring function"""
    print("🚀 Starting OptionsAgents Live Monitor...")
    
    # Initialize monitor
    monitor = OptionsAgentsMonitor()
    
    # Show initial dashboard
    monitor.display_dashboard()
    monitor.detailed_gamma_analysis()
    
    # Ask user if they want continuous monitoring
    print(f"\nOptions:")
    print(f"1. One-time check (done)")
    print(f"2. Continuous monitoring (refreshes every 10s)")
    
    choice = input("\nSelect option (1 or 2): ").strip()
    
    if choice == "2":
        print("\n🔄 Starting continuous monitoring...")
        print("Press Ctrl+C to stop")
        try:
            asyncio.run(monitor.continuous_monitor())
        except KeyboardInterrupt:
            print("\n👋 Goodbye!")


if __name__ == "__main__":
    main()