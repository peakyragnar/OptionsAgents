#!/bin/bash
# Switch between regular Options Agents and with Gamma Tool Sam

echo "🎯 Options Agents Service Switcher"
echo "================================="
echo ""
echo "Choose mode:"
echo "1) Regular mode (without Gamma Tool Sam)"
echo "2) With Gamma Tool Sam integration"
echo ""
read -p "Enter choice (1 or 2): " choice

case $choice in
  1)
    echo "Switching to regular mode..."
    # Stop both services
    launchctl unload -w ~/Library/LaunchAgents/com.optionsagents.live.plist 2>/dev/null
    launchctl unload -w ~/Library/LaunchAgents/com.optionsagents.live.gamma.plist 2>/dev/null
    
    # Start regular service
    launchctl load -w ~/Library/LaunchAgents/com.optionsagents.live.plist
    echo "✅ Started regular Options Agents service"
    ;;
  2)
    echo "Switching to Gamma Tool Sam mode..."
    # Stop both services
    launchctl unload -w ~/Library/LaunchAgents/com.optionsagents.live.plist 2>/dev/null
    launchctl unload -w ~/Library/LaunchAgents/com.optionsagents.live.gamma.plist 2>/dev/null
    
    # Start Gamma Tool Sam service
    launchctl load -w ~/Library/LaunchAgents/com.optionsagents.live.gamma.plist
    echo "✅ Started Options Agents with Gamma Tool Sam"
    echo "   Dashboard available at: http://localhost:8080"
    ;;
  *)
    echo "Invalid choice"
    exit 1
    ;;
esac

echo ""
echo "Current services:"
launchctl list | grep optionsagents