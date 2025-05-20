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