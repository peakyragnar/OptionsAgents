#!/usr/bin/env python3
"""
Reliable Snapshot Scheduler
Runs snapshots at appropriate intervals with proper error handling
"""

import time
import datetime
import subprocess
import sys
import os
import logging
from pathlib import Path
import pytz

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.utils.logging_config import setup_application_logging, setup_component_logger

# Set up logging
setup_application_logging()
logger = setup_component_logger("snapshot_scheduler")

def is_market_open():
    """Check if market is open"""
    et_tz = pytz.timezone('US/Eastern')
    now = datetime.datetime.now(et_tz)
    
    # Skip weekends
    if now.weekday() >= 5:
        return False
    
    # Market hours: 9:30 AM - 4:00 PM ET
    market_open = now.replace(hour=9, minute=30, second=0)
    market_close = now.replace(hour=16, minute=0, second=0)
    
    return market_open <= now <= market_close

def get_last_snapshot_time():
    """Get timestamp of most recent snapshot"""
    today = datetime.date.today()
    snapshot_dir = Path(f"data/parquet/spx/date={today}")
    
    if not snapshot_dir.exists():
        return None
    
    # Find most recent file
    files = list(snapshot_dir.glob("*.parquet"))
    if not files:
        return None
    
    latest = max(files, key=lambda f: f.stat().st_mtime)
    return datetime.datetime.fromtimestamp(latest.stat().st_mtime)

def run_snapshot():
    """Run the snapshot process"""
    logger.info("Running snapshot...")
    
    try:
        # Run the fixed snapshot script
        result = subprocess.run(
            [sys.executable, "-m", "src.ingest.snapshot_fixed"],
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout
        )
        
        if result.returncode == 0:
            logger.info("Snapshot completed successfully")
            return True
        else:
            logger.error(f"Snapshot failed with code {result.returncode}")
            logger.error(f"STDOUT: {result.stdout}")
            logger.error(f"STDERR: {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        logger.error("Snapshot timed out after 5 minutes")
        return False
    except Exception as e:
        logger.error(f"Failed to run snapshot: {e}")
        return False

def main():
    """Main scheduler loop"""
    logger.info("=" * 60)
    logger.info("Starting Snapshot Scheduler")
    logger.info("=" * 60)
    
    # Configuration
    MARKET_HOURS_INTERVAL = 60  # 1 minute during market hours
    OFF_HOURS_INTERVAL = 3600   # 1 hour outside market hours
    MIN_SNAPSHOT_AGE = 50       # Don't snapshot if last one is < 50 seconds old
    
    consecutive_failures = 0
    max_consecutive_failures = 5
    
    while True:
        try:
            # Check if we should run a snapshot
            should_run = False
            reason = ""
            
            # Get last snapshot time
            last_snapshot = get_last_snapshot_time()
            
            if last_snapshot:
                age_seconds = (datetime.datetime.now() - last_snapshot).total_seconds()
                
                if age_seconds < MIN_SNAPSHOT_AGE:
                    reason = f"Last snapshot too recent ({age_seconds:.0f}s ago)"
                elif is_market_open() and age_seconds > MARKET_HOURS_INTERVAL:
                    should_run = True
                    reason = "Market hours snapshot due"
                elif not is_market_open() and age_seconds > OFF_HOURS_INTERVAL:
                    should_run = True
                    reason = "Off-hours snapshot due"
                else:
                    reason = f"Not time yet (age: {age_seconds:.0f}s)"
            else:
                should_run = True
                reason = "No snapshot found for today"
            
            # Run snapshot if needed
            if should_run:
                logger.info(f"Snapshot triggered: {reason}")
                
                if run_snapshot():
                    consecutive_failures = 0
                else:
                    consecutive_failures += 1
                    logger.warning(f"Snapshot failed ({consecutive_failures}/{max_consecutive_failures})")
                    
                    if consecutive_failures >= max_consecutive_failures:
                        logger.critical("Too many consecutive failures. Exiting.")
                        sys.exit(1)
            else:
                logger.debug(f"Skipping snapshot: {reason}")
            
            # Sleep based on market status
            if is_market_open():
                sleep_time = 30  # Check every 30 seconds during market
            else:
                sleep_time = 300  # Check every 5 minutes off-hours
            
            time.sleep(sleep_time)
            
        except KeyboardInterrupt:
            logger.info("Scheduler stopped by user")
            break
        except Exception as e:
            logger.error(f"Scheduler error: {e}", exc_info=True)
            time.sleep(60)  # Wait a minute before retrying

if __name__ == "__main__":
    main()