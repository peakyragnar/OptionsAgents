#!/bin/bash
# Migration script to fix the snapshot system

echo "=========================================="
echo "MIGRATING TO FIXED SNAPSHOT SYSTEM"
echo "=========================================="

# 1. Make scripts executable
echo "1. Setting permissions..."
chmod +x scripts/run_snapshot_scheduler.py
chmod +x test_snapshot_system.py

# 2. Update the existing snapshot script to use the fixed version
echo "2. Updating snapshot module..."
cat > src/ingest/snapshot.py << 'EOF'
"""
Redirect to the fixed snapshot implementation
"""
from .snapshot_fixed import *

# Maintain backward compatibility
if __name__ == "__main__":
    import sys
    sys.exit(0 if main() else 1)
EOF

# 3. Update the intraday snapshot script
echo "3. Updating run_intraday_snapshot.sh..."
cat > run_intraday_snapshot.sh << 'EOF'
#!/bin/zsh
source ~/.zprofile
cd /Users/michael/OptionsAgents
source .venv/bin/activate
python -m src.ingest.snapshot_fixed
EOF
chmod +x run_intraday_snapshot.sh

# 4. Create a systemd/launchd service file for macOS
echo "4. Creating LaunchAgent plist..."
mkdir -p ~/Library/LaunchAgents

cat > ~/Library/LaunchAgents/com.optionsagents.snapshot.plist << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.optionsagents.snapshot</string>
    <key>ProgramArguments</key>
    <array>
        <string>/Users/michael/OptionsAgents/.venv/bin/python</string>
        <string>/Users/michael/OptionsAgents/scripts/run_snapshot_scheduler.py</string>
    </array>
    <key>WorkingDirectory</key>
    <string>/Users/michael/OptionsAgents</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/usr/local/bin:/usr/bin:/bin</string>
    </dict>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/Users/michael/logs/OptionsAgents/snapshot_scheduler.log</string>
    <key>StandardErrorPath</key>
    <string>/Users/michael/logs/OptionsAgents/snapshot_scheduler_error.log</string>
</dict>
</plist>
EOF

echo ""
echo "=========================================="
echo "MIGRATION COMPLETE!"
echo "=========================================="
echo ""
echo "Next steps:"
echo "1. Test the system: python test_snapshot_system.py"
echo "2. Start scheduler manually: python scripts/run_snapshot_scheduler.py"
echo "3. Or start as service: launchctl load ~/Library/LaunchAgents/com.optionsagents.snapshot.plist"
echo ""
echo "To stop service: launchctl unload ~/Library/LaunchAgents/com.optionsagents.snapshot.plist"