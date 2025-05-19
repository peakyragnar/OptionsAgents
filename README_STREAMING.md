# OptionsAgents Streaming Layer

This document describes how to use the real-time options data streaming functionality in OptionsAgents.

## Overview

The streaming layer consists of:

1. A data source (WebSocket or REST API simulation)
2. An intraday snapshot generator that runs every 5 minutes
3. A dealer gamma live tool that analyzes the latest intraday snapshot

## Setup

1. Ensure your Polygon.io API key is in `.env` (same key used for the existing snapshot functionality)
2. Install dependencies: `pip install -r requirements.txt`
3. The LaunchAgent has been installed to run the intraday snapshot every 5 minutes

## Usage

### Start the Data Collection

To start receiving options data:

```bash
# Try WebSocket first (requires paid Polygon.io plan with WebSocket access)
./run_stream.sh

# OR force REST API simulation mode
./run_stream.sh --rest
```

This will start collecting quotes and trades for SPX options.

### Manually Generate an Intraday Snapshot

To manually generate an intraday snapshot:

```bash
./run_intraday_snapshot.sh
```

This will create a Parquet file in `data/intraday/` with the current dealer positions and gamma calculations.

### View Live Dealer Gamma

To view the live dealer gamma calculations:

```bash
./run_dealer_gamma_live.sh
```

This will display the total dealer gamma, gamma flip level, and detailed breakdown by strike.

## Data Sources

The system supports two data sources:

1. **WebSocket API** (requires paid Polygon.io plan)
   - Real-time streaming of option quotes and trades
   - Connects directly to Polygon.io's options WebSocket API

2. **REST API Simulation** (fallback)
   - Periodically fetches options data via REST API
   - Simulates trading activity based on real option chains
   - Used automatically if WebSocket connection fails
   - Can be forced with `USE_REST=true`

## Data Storage

- Intraday snapshots are stored in `data/intraday/` with timestamp-based filenames
- Each file contains dealer positions and gamma calculations at the strike level

## Integration

- The existing overnight dealer gamma (`src/tools/dealer_gamma.py`) uses end-of-day positions
- The new live dealer gamma (`src/tools/dealer_gamma_live.py`) uses intraday positions

## Testing

Run the tests to verify everything is working:

```bash
python -m pytest tests/test_live_gamma_exists.py -v
python -m pytest tests/test_ws_client_classify.py -v
```

Note: The live gamma test will be skipped if no intraday snapshots are available yet.