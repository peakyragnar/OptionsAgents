#!/usr/bin/env python3
"""Watch for new snapshot files and try to catch what creates them"""

import os
import time
import subprocess
from pathlib import Path
from datetime import datetime

snapshot_dir = Path("data/parquet/spx/date=2025-05-29")
seen_files = set(snapshot_dir.glob("*.parquet"))

print(f"Watching {snapshot_dir} for new files...")
print(f"Currently {len(seen_files)} files")

while True:
    current_files = set(snapshot_dir.glob("*.parquet"))
    new_files = current_files - seen_files
    
    if new_files:
        for f in new_files:
            print(f"\n🆕 NEW FILE: {f.name} at {datetime.now().strftime('%H:%M:%S')}")
            
            # Check what processes are running
            ps_output = subprocess.run(['ps', 'aux'], capture_output=True, text=True)
            for line in ps_output.stdout.splitlines():
                if any(keyword in line.lower() for keyword in ['snapshot', 'ingest', 'run_once', 'optionsagents']):
                    if 'grep' not in line and 'watch_snapshots' not in line:
                        print(f"   PROCESS: {line[:150]}")
            
            # Check recent launchctl activity
            launchctl = subprocess.run(['launchctl', 'list'], capture_output=True, text=True)
            for line in launchctl.stdout.splitlines():
                if 'optionsagents' in line:
                    print(f"   LAUNCHCTL: {line}")
                    
        seen_files = current_files
    
    time.sleep(5)