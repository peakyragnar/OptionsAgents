#!/bin/bash

# System monitoring for OptionsAgents
ALERT_THRESHOLD_GB=10  # Alert if any log file exceeds this size

check_large_files() {
    echo "=== Large Log Files Check ==="
    large_files=$(find ~/logs -type f -size +${ALERT_THRESHOLD_GB}G 2>/dev/null)
    
    if [ -n "$large_files" ]; then
        echo "⚠️  WARNING: Large log files detected:"
        echo "$large_files" | while read file; do
            size=$(ls -lah "$file" | awk '{print $5}')
            echo "  - $file ($size)"
        done
        
        # Send alert (customize as needed)
        echo "Large log files detected in OptionsAgents" | mail -s "Log Alert" your-email@domain.com 2>/dev/null || true
    else
        echo "✅ No oversized log files found"
    fi
}

check_disk_space() {
    echo "=== Disk Space Check ==="
    disk_usage=$(df -h | grep -E "/$" | awk '{print $5}' | sed 's/%//')
    
    if [ "$disk_usage" -gt 85 ]; then
        echo "⚠️  WARNING: Disk usage is ${disk_usage}%"
    else
        echo "✅ Disk usage is healthy (${disk_usage}%)"
    fi
}

check_running_processes() {
    echo "=== OptionsAgents Processes ==="
    processes=$(ps aux | grep -E "python.*OptionsAgents" | grep -v grep)
    
    if [ -n "$processes" ]; then
        echo "Running processes:"
        echo "$processes"
    else
        echo "No OptionsAgents processes currently running"
    fi
}

# Run all checks
echo "OptionsAgents System Monitor - $(date)"
echo "========================================="
check_large_files
echo
check_disk_space
echo
check_running_processes
echo "========================================="