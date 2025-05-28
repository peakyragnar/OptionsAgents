#!/bin/bash

# OptionsAgents Log Cleanup Script
# This script manages log files to prevent disk space issues

LOG_DIR="$HOME/logs"
OPTIONSAGENTS_LOG_DIR="$LOG_DIR/OptionsAgents"

# Function to log with timestamp
log_message() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

log_message "Starting log cleanup for OptionsAgents"

# Create cleanup log
CLEANUP_LOG="$LOG_DIR/cleanup.log"
exec 1> >(tee -a "$CLEANUP_LOG")
exec 2>&1

# 1. Remove logs older than 30 days
log_message "Removing logs older than 30 days..."
find "$OPTIONSAGENTS_LOG_DIR" -type f -name "*.log*" -mtime +30 -delete

# 2. Compress logs older than 7 days
log_message "Compressing logs older than 7 days..."
find "$OPTIONSAGENTS_LOG_DIR" -type f -name "*.log" -mtime +7 ! -name "*.gz" -exec gzip {} \;

# 3. Remove any files larger than 1GB (emergency cleanup)
log_message "Checking for oversized log files..."
find "$LOG_DIR" -type f -size +1G -exec ls -lah {} \; -exec rm -f {} \;

# 4. Check disk usage
log_message "Current disk usage:"
df -h | grep -E "Filesystem|/$"

# 5. Log directory sizes
log_message "Log directory sizes:"
du -sh "$LOG_DIR"/* 2>/dev/null | sort -hr

log_message "Log cleanup completed"