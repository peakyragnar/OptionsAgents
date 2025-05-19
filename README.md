# Options Agents

Tools for real-time options data collection, analysis, and dealer gamma visualization.

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

3. Create a `.env` file with your Polygon.io API key:
   ```
   POLYGON_KEY=your_polygon_api_key_here
   ```

## Data Collection

### One-time Snapshot

To capture a single snapshot of the SPX options chain:

```bash
python -m src.ingest.snapshot
```

This saves data to `data/parquet/spx/date=YYYY-MM-DD/HH_MM_SS.parquet`

### Streaming Real-time Data

To stream real-time options data and build dealer positioning:

```bash
python -m src.stream.run_ws_with_snapshots
```

This will:
1. Connect to Polygon.io WebSocket API
2. Process options quotes and trades
3. Track dealer positioning in real-time
4. Save snapshots every 5 minutes to `data/intraday/`

### Fallback REST Simulator

If the WebSocket isn't working or you need to test without live data:

```bash
USE_REST=true python -m src.stream.rest_simulator
```

## Analysis Tools

### Dealer Gamma Calculator

Calculate dealer gamma exposure from option chain data:

```bash
python -m src.tools.dealer_gamma
```

### View Recreation

If you need to recreate DuckDB views with proper column types:

```bash
python -m src.tools.recreate_views
```

## Options Greeks 

Options Greeks are calculated using the Black-Scholes model in `src.utils.greeks`.

The following Greeks are supported:
- Delta
- Gamma
- Vega
- Theta

## Troubleshooting

### WebSocket Connection Issues

1. Verify your API key in the `.env` file
2. Check if US markets are open (9:30 AM - 4:00 PM ET, weekdays)
3. Ensure your network allows WebSocket connections

### Missing or Zero Gamma Values

If gamma values are zero or missing, verify:
1. Data types are properly cast to DOUBLE in DuckDB
2. Implied volatility values are valid (not NULL or zero)
3. Time to expiry is properly calculated