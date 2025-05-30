# 🎯 How to Run Gamma Tool Sam - Simple Guide

## The Current Situation

You already have the main Options Agents system running via launchd (PID 39025). Now you want to add Gamma Tool Sam to see the directional analysis dashboard.

## Method 1: Stop Current Service, Start New One (RECOMMENDED)

```bash
# Stop the current service
launchctl unload -w ~/Library/LaunchAgents/com.optionsagents.live.plist

# Start the service WITH Gamma Tool Sam
launchctl load -w ~/Library/LaunchAgents/com.optionsagents.live.gamma.plist
```

Then open: http://localhost:8080

## Method 2: Use the Switcher Script (EASIEST)

```bash
./switch_gamma_mode.sh
```
- Choose option 2
- It will handle stopping/starting for you

## Method 3: Run Manually (FOR TESTING)

If you want to test it first:

```bash
# Stop the current service first
launchctl unload -w ~/Library/LaunchAgents/com.optionsagents.live.plist

# Run manually with Gamma Tool Sam
python -m src.cli live --gamma-tool-sam
```

## What Each Method Does

- **Method 1 & 2**: Replaces your current service with one that includes Gamma Tool Sam
- **Method 3**: Runs in your terminal so you can see the output

## Dashboard Features

Once running, go to http://localhost:8080 to see:
- Net directional force (green = up, red = down)
- Trading signals (LONG/SHORT/WAIT)
- Pin levels acting as magnets
- Live trade count and statistics

## To Go Back to Normal Mode

```bash
./switch_gamma_mode.sh
```
Choose option 1

## Quick Check

To see what's currently running:
```bash
launchctl list | grep optionsagents
```

## Common Issues

1. **Port 8080 in use**: Something else is using the port
2. **No data showing**: Markets closed or no trades yet
3. **Can't connect**: Make sure the service started successfully

## The Bottom Line

Since you already have a service running, the easiest way is:
```bash
./switch_gamma_mode.sh
# Press 2
# Open http://localhost:8080
```

That's it! 🎯