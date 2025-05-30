# 🎯 Gamma Tool Sam

Real-time directional analysis for 0DTE SPX options using dealer gamma flows.

## Overview

Gamma Tool Sam analyzes option order flow to detect directional pressure from dealer hedging activity. It provides:

- **Directional Force Indicators**: Tracks upward/downward gamma pressure
- **Pin Detection**: Identifies strikes acting as magnets or barriers  
- **Dynamic Thresholds**: Time-based gamma thresholds (25K morning → 400K EOD)
- **Premium Signals**: Suggests premium selling strategies in low gamma environments
- **Real-time Dashboard**: Web interface with live updates

## Quick Start

### Option 1: Integrated Mode (Recommended)

Run both systems together in one process:
```bash
./run_with_gamma_sam.sh
```

Or manually:
```bash
python -m src.cli live --gamma-tool-sam
```

This runs everything in one process with proper trade queue sharing.

### Option 2: Standalone Dashboard (Display Only)

For testing the dashboard without trades:
```bash
python gamma_sam_standalone.py
```

Then open your browser to http://localhost:8080

### Web Dashboard Access

Once running, the dashboard is available at:
- **URL**: http://localhost:8080
- **Updates**: Every 2 seconds
- **Features**: Real-time gamma visualization, directional signals, pin detection

## Features

### Dynamic Gamma Thresholds

Time-based thresholds that adapt throughout the trading day:
- **9:30-10:00 AM**: 25K (morning positioning)
- **10:00-11:00 AM**: 75K (building positions)
- **11:00-12:00 PM**: 150K (increasing activity)
- **12:00-2:00 PM**: 300K (lunch continuation)
- **2:00-3:30 PM**: 350K (afternoon activity)
- **3:30-4:00 PM**: 400K (end of day)

### Premium Selling Strategies

When gamma is low (below threshold), suggests:
- **SELL_STRADDLE**: High confidence in range-bound movement
- **SELL_IRON_CONDOR**: Medium confidence, defined risk
- **SELL_BUTTERFLY**: Lower confidence, limited risk

### Directional Signals

- **LONG**: Strong upward force detected (3 momentum bars + high confidence)
- **SHORT**: Strong downward force detected  
- **WAIT**: Insufficient clarity or conflicting signals

## Technical Details

### Gamma Calculation

Uses Black-Scholes model for option gamma:
```
Gamma = e^(-d1²/2) / (S * σ * √(2π * t))
```

### Directional Classification

- **Upward Force**: Calls above SPX, puts at/above SPX (squeeze up)
- **Downward Force**: Puts below SPX, calls at/below SPX (pressure down)

### Integration Architecture

- Connects to main system's `TRADE_Q` asyncio queue
- Processes trades in real-time
- Updates dashboard via Flask REST API

## Troubleshooting

1. **"Trade queue not available"**: Use integrated mode (`--gamma-tool-sam` flag)
2. **No trades showing**: Check that markets are open (9:30 AM - 4:00 PM ET)
3. **Dashboard not loading**: Check port 8080 is not in use
4. **Integration issues**: Make sure gamma_tool_sam directory is in Python path

## Architecture Notes

- **Integrated Mode**: Runs within the main process, shares asyncio queues directly
- **Standalone Mode**: Runs separately, no trade processing (display only)
- **Trade Flow**: Polygon WebSocket → TRADE_Q → Gamma Tool Sam → Dashboard

## API Endpoints

- `GET /`: Dashboard HTML
- `GET /api/data`: Current state JSON
- `GET /api/alerts`: Recent alerts
- `GET /api/stats`: Statistics

## Requirements

- Python 3.8+
- Options Agents system
- Polygon.io API key (for SPX prices)
- Port 8080 available