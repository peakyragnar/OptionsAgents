# Options Agents - Overview and Usage Guidelines

This document provides an overview of the Options Agents project as of the latest update. Use this as a reference for the project's architecture, setup, and usage.

## Current Project State

The Options Agents project has evolved into a comprehensive system for real-time options market data processing and dealer gamma exposure tracking. Below is the current README content that reflects the latest state of the project.

---

# Options Agents

Real-time options market data processing and dealer gamma exposure tracking.

## Architecture

The system consists of several key components:

1. **Data Collection**
   - Snapshots: Daily options chain capture to Parquet files
   - Quote Cache: Real-time NBBO quotes for options
   - Trade Feed: WebSocket connection to Polygon.io options trades

2. **Processing Engine**
   - Dealer Engine: Classifies trades and calculates gamma exposure
   - Strike Book: Tracks positions and gamma by strike price
   - Volatility Surface: Caches and calculates implied volatility

3. **Persistence**
   - DuckDB: Stores dealer gamma snapshots for analysis
   - Parquet: Stores option chain data efficiently

## Setup

1. Create a Python virtual environment:
   ```bash
   python -m venv .venv
   source .venv/bin/activate
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Create a `.env` file with your API keys:
   ```
   POLYGON_KEY=your_polygon_api_key_here
   OA_GAMMA_DB=path/to/your/database.db  # Optional, defaults to data/intraday.db
   ```

## Command Line Interface

The system provides a Typer-based CLI:

```bash
python -m src.cli live
```

This launches the complete system:
- Quote cache for real-time option quotes
- Trade feed for streaming trades from Polygon
- Dealer engine for processing trades and calculating gamma
- Automatic snapshots saved to DuckDB

### Offline Replay

For back-testing with historical data:

```bash
python -m src.cli replay path/to/trades.parquet
```

## Data Collection

### One-time Snapshot

Capture a snapshot of the SPX options chain:

```bash
python -m src.ingest.snapshot
```

This saves data to `data/parquet/spx/date=YYYY-MM-DD/HH_MM_SS.parquet`

### Quote Cache

The quote cache maintains the latest NBBO (National Best Bid and Offer) for all options:

```python
from src.stream.quote_cache import quotes, run as quotes_run
# quotes is a dict mapping symbols to (bid, ask, timestamp) tuples
```

### Trade Feed

The trade feed streams option trades from Polygon.io:

```python
from src.stream.trade_feed import TRADE_Q, run as trades_run
# TRADE_Q is an asyncio.Queue of trade dictionaries
```

## Dealer Gamma Engine

The engine processes trades by:
1. Classifying them as BUY/SELL based on NBBO
2. Calculating option gamma using Black-Scholes
3. Tracking dealer position and gamma exposure
4. Generating periodic snapshots of gamma exposure

```python
from src.dealer.engine import run as engine_run, _book
# _book contains the current state of dealer positions
```

## Options Greeks

Options Greeks are calculated using the Black-Scholes model in `src.utils.greeks`:

```python
from src.utils.greeks import gamma, implied_vol_call, implied_vol_put
```

Supported Greeks:
- Delta: Option price sensitivity to underlying price
- Gamma: Rate of change of delta (key for dealer hedging)
- Vega: Option price sensitivity to volatility
- Theta: Option price decay over time

## Troubleshooting

### WebSocket Connection Issues

1. Verify your API key in the `.env` file
2. Check if US markets are open (9:30 AM - 4:00 PM ET, weekdays)
3. Connection failures are handled automatically with reconnection logic

### Database Configuration

- Set `OA_GAMMA_DB` environment variable to customize the database location
- The DB is auto-created on first run
- Use read-only connections for analysis to avoid conflicts

---

## Development History

The project has evolved through several phases:
1. Initial setup with basic data collection
2. Addition of DuckDB for analytics
3. Implementation of WebSocket streaming for real-time data
4. Development of dealer gamma calculations
5. Integration of all components with a CLI interface

## Future Enhancements

Potential areas for future development:
1. Add visualization tools for gamma exposure
2. Implement strategy recommendation based on dealer gamma
3. Integrate with trading platforms for execution
4. Add more sophisticated analytics and machine learning models

## Testing

Run the tests to ensure everything is working correctly:

```bash
# Run all tests
python -m pytest

# Run core system tests only
python run_core_tests.py

# Quick test suite (bash)
./pytest.sh
```

## System Monitoring

Check system health with the consolidated status script:

```bash
# Check all system components
python system_status.py

# Quick monitor (legacy)
python simple_monitor.py
```

## Troubleshooting

### Common Issues

1. **SPX Price Shows Fallback ($5,908.28 or $5,920.00)**
   - Check Polygon API key is set: `echo $POLYGON_KEY`
   - Test API directly: `python test_spx_price.py`
   - Check snapshot logs: `tail /Users/michael/logs/OptionsAgents/components/src.ingest.snapshot_fixed.log`

2. **Snapshots Not Being Created**
   - Check service status: `launchctl list | grep optionsagents`
   - Restart snapshot service: `launchctl unload -w ~/Library/LaunchAgents/com.optionsagents.snapshot.plist && launchctl load -w ~/Library/LaunchAgents/com.optionsagents.snapshot.plist`
   - Check for conflicting services: Make sure `com.optionsagents.ingest.plist.disabled` exists

3. **Test Suite Issues**
   - For 0DTE options: Tests expect 100-500 strikes, not 450+
   - For pre-market: Zero open interest is normal and tests will skip
   - For missing columns: Ensure snapshots include vega, theta, delta, date

4. **Services Showing "NOT RUNNING"**
   - Snapshot service is scheduled (runs every 60s then exits) - this is normal
   - Live service should stay running - restart if crashed
   - Use `python system_status.py` for accurate service status

### Key System Components

- **Snapshot Service**: Runs every 60 seconds via launchd, creates parquet files with 0DTE options
- **Live Service**: Continuous trading engine processing real-time option trades  
- **Test Suite**: Organized into core tests (always run) and optional tests
- **Monitoring**: Multiple scripts available for different detail levels