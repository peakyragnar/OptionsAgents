#!/bin/bash
set -e  # Exit on any error

# Set working directory
cd /Users/michael/OptionsAgents

# Set environment variables
export POLYGON_KEY=wpVD1X01KQu8pQMp34clrAKQWxTXrB8A
export PYTHONPATH=/Users/michael/OptionsAgents
export PATH=/Users/michael/OptionsAgents/.venv/bin:$PATH

# Log execution
echo "$(date): Starting snapshot creation..." >> /Users/michael/logs/cron_snapshot.log

# Run the snapshot with proper error handling using absolute module path
PYTHONPATH=/Users/michael/OptionsAgents /Users/michael/OptionsAgents/.venv/bin/python -m src.ingest.snapshot_fixed 2>&1 || {
    echo "$(date): Snapshot failed with exit code $?" >> /Users/michael/logs/cron_snapshot.log
    exit 1
}

echo "$(date): Snapshot completed successfully" >> /Users/michael/logs/cron_snapshot.log