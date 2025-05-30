# Options Agents System Architecture - Complete Flow

## System Overview

```
┌─────────────────────────────────────────────────────────────────────────────────────┐
│                              OPTIONS AGENTS SYSTEM FLOW                              │
└─────────────────────────────────────────────────────────────────────────────────────┘

1. SNAPSHOT SYSTEM (Runs every 60 seconds via launchd)
   └─> src/ingest/snapshot_fixed.py
       ├─> Gets SPX options chain from Polygon API
       ├─> Calculates IMPLIED VOLATILITY for each option
       ├─> Calculates all Greeks (gamma, vega, theta, delta) using Black-Scholes
       ├─> Gets real SPX price during market hours (not fallback!)
       └─> Saves to: data/parquet/spx/date=YYYY-MM-DD/HH_MM_SS.parquet

2. LIVE TRADING SYSTEM (Started with: python -m src.cli live --gamma-tool-sam)
   │
   ├─> Symbol Loading (src/cli.py)
   │   └─> Loads latest snapshot parquet file
   │   └─> Filters to realistic strikes (±200 points from SPX)
   │   └─> Adds I:SPX for real-time index quotes
   │
   ├─> Unified WebSocket Feed (src/stream/unified_feed.py)
   │   ├─> Connects to Polygon WebSocket: wss://socket.polygon.io/options
   │   ├─> Subscribes to T.* (trades) and Q.* (quotes) for all symbols
   │   ├─> Updates quote cache with NBBO
   │   └─> Pushes trades to shared queue
   │
   ├─> Shared Queue (src/stream/shared_queue.py) <── CRITICAL FIX!
   │   └─> Lazy initialization ensures correct event loop binding
   │   └─> Connects unified feed → dealer engine
   │
   ├─> Dealer Engine (src/dealer/engine.py)
   │   ├─> Consumes trades from shared queue
   │   ├─> Classifies trades as BUY/SELL based on NBBO
   │   ├─> Calculates gamma using Black-Scholes
   │   ├─> Updates dealer position (StrikeBook)
   │   └─> Saves snapshots to database every second
   │
   └─> Gamma Tool Sam Integration (gamma_tool_sam/)
       ├─> Processes same trades for directional analysis
       ├─> Calculates pin levels and forces
       └─> Serves dashboard on http://localhost:8080

3. PERSISTENCE LAYER
   ├─> data/intraday.db (or data/live.db)
   │   └─> Table: intraday_gamma (ts, dealer_gamma)
   │
   └─> market.duckdb
       └─> Table: spx_chain (snapshot data with full Greeks)

4. TESTING & MONITORING SCRIPTS
   ├─> system_status.py         # Comprehensive system health check
   ├─> test_live_gamma.py       # View current dealer gamma from DB
   ├─> simple_monitor.py        # Basic monitoring output
   ├─> check_snapshot_gamma.py  # Debug snapshot gamma values
   ├─> watch_snapshots.py       # Monitor snapshot creation
   ├─> debug_gamma.py           # Debug gamma calculations
   ├─> check_recent_trades.py   # View recent option trades
   ├─> run_dealer_gamma.py      # Gamma visualization from snapshots
   ├─> test_gamma_now.py        # Test gamma calculations
   ├─> test_dashboard_now.py    # Test dashboard directly
   │
   ├─> Test Suites:
   │   ├─> run_core_tests.py    # Run essential tests only
   │   ├─> pytest.sh            # Quick pytest runner
   │   ├─> run_tests.sh         # Full test suite
   │   └─> tests/
   │       ├─> test_dealer_gamma.py         # Gamma calculation tests
   │       ├─> test_snapshot.py             # Snapshot system tests
   │       ├─> test_ws_client.py            # WebSocket tests
   │       ├─> test_quote_cache.py          # Quote cache tests
   │       ├─> test_trade_feed.py           # Trade feed tests
   │       ├─> test_engine.py               # Dealer engine tests
   │       ├─> test_strike_book.py          # Strike book tests
   │       ├─> test_surface.py              # Volatility surface tests
   │       ├─> test_greeks_values.py        # Greeks calculation tests
   │       ├─> test_data_quality.py         # Data quality checks
   │       ├─> test_required_columns.py     # Column validation
   │       └─> test_snapshot_file_exists.py # File system tests
   │
   └─> Diagnostic Tools:
       ├─> diagnose_queue.py     # Debug queue issues
       ├─> test_async_issue.py   # Test async problems
       └─> streaming_integration.py # Test streaming
```

## Detailed Component Flow

### 1. Snapshot Collection (Scheduled)
```
launchd (every 60s) 
  └─> run_snapshot_cron.sh
      └─> python -m src.ingest.snapshot_fixed
          ├─> Gets SPX options chain from Polygon
          ├─> For each option:
          │   ├─> Calculate implied volatility
          │   ├─> Calculate gamma using Black-Scholes
          │   ├─> Calculate vega, theta, delta
          │   └─> Get volume and open interest
          ├─> Gets real SPX price (market hours) or previous close
          └─> Saves parquet with columns:
              - strike, type, bid, ask, volume, open_interest
              - iv, gamma, vega, theta, delta
              - under_px (SPX price), date, ts
```

### 2. Live Trading System
```
python -m src.cli live [--gamma-tool-sam]
  │
  ├─> Load Symbols
  │   └─> load_symbols_from_snapshot()
  │       ├─> Find latest parquet file
  │       ├─> Filter strikes: SPX ± 200 points
  │       └─> Return: ['O:SPXW250530C05900000', ..., 'I:SPX']
  │
  ├─> Create Async Tasks
  │   ├─> Dealer Engine Task
  │   │   └─> engine_run(append_gamma)
  │   │       └─> Processes trades, calculates gamma
  │   │
  │   ├─> Unified Feed Task
  │   │   └─> unified_run(symbols)
  │   │       └─> WebSocket streaming quotes + trades
  │   │
  │   └─> [Optional] Gamma Tool Sam Task
  │       └─> run_gamma_tool_sam(engine, trade_queue)
  │           └─> Dashboard + directional analysis
  │
  └─> Main Event Loop
      └─> Runs until Ctrl+C
```

### 3. Trade Processing Pipeline
```
Polygon WebSocket
  │
  ├─> Quote (Q) Message
  │   └─> Update quote_cache[symbol] = {bid, ask, ts}
  │
  └─> Trade (T) Message
      └─> unified_feed._handle_trade()
          ├─> Classify: BUY/SELL/? using NBBO
          └─> Push to shared_queue
              │
              └─> dealer/engine.run()
                  └─> while True:
                      ├─> trade = await trade_queue.get()
                      └─> _process_trade(trade)
                          ├─> Parse OCC symbol
                          ├─> Get SPX price from quotes
                          ├─> Calculate IV using VolSurface
                          ├─> Calculate gamma (Black-Scholes)
                          ├─> Update StrikeBook
                          │   └─> Dealer gamma = -customer gamma
                          └─> Every 1s: append_gamma(ts, total_gamma)
                              └─> INSERT INTO intraday_gamma
```

### 4. Key Scripts and Their Purposes

```
MAIN ENTRY POINTS:
- src/cli.py                    # Main entry point with Typer CLI
- src/ingest/snapshot_fixed.py  # Captures option chain snapshots with Greeks
- src/stream/unified_feed.py    # WebSocket for quotes + trades
- src/stream/shared_queue.py    # Queue with lazy initialization (FIX!)
- src/dealer/engine.py          # Processes trades, calculates gamma
- src/persistence.py            # Database operations

GAMMA TOOL SAM:
- gamma_tool_sam/integration.py         # Connects to main system
- gamma_tool_sam/gamma_engine.py        # Core analysis engine
- gamma_tool_sam/dashboard/web_dashboard.py # Flask web UI
- gamma_tool_sam/core/position_tracker.py  # Track positions
- gamma_tool_sam/core/gamma_calculator.py  # Calculate gamma
- gamma_tool_sam/core/change_detector.py   # Detect market changes

MONITORING & TESTING:
- system_status.py              # Check all components health
- test_live_gamma.py            # View current gamma from DB
- simple_monitor.py             # Basic system monitoring
- check_snapshot_gamma.py       # Verify snapshot gamma values
- watch_snapshots.py            # Monitor snapshot creation
- debug_gamma.py                # Debug gamma calculations
- test_dashboard_now.py         # Test dashboard directly

LAUNCHERS & UTILITIES:
- run_snapshot_cron.sh          # Cron wrapper for snapshots
- run_stream.sh                 # Start live trading
- run_dealer_gamma.py           # Visualize dealer gamma
- run_dealer_gamma_live.sh      # Live gamma monitoring
- run_core_tests.py             # Run essential tests only
```

### 5. Database Schema

```sql
-- DuckDB: market.duckdb
CREATE TABLE spx_chain (
    strike INTEGER,
    type VARCHAR,           -- 'C' or 'P'
    bid DOUBLE,
    ask DOUBLE,
    volume INTEGER,
    open_interest INTEGER,
    iv DOUBLE,             -- Implied volatility
    gamma DOUBLE,          -- Option gamma (calculated)
    vega DOUBLE,           -- Option vega (calculated)
    theta DOUBLE,          -- Option theta (calculated)
    delta DOUBLE,          -- Option delta (calculated)
    under_px DOUBLE,       -- SPX price at snapshot time
    expiry VARCHAR,        -- Expiry date
    filename VARCHAR,      -- Parquet filename
    date DATE,
    ts VARCHAR             -- HH_MM_SS
);

-- DuckDB: data/intraday.db (or data/live.db)
CREATE TABLE intraday_gamma (
    ts DOUBLE,             -- Unix timestamp
    dealer_gamma DOUBLE    -- Net dealer gamma from trades
);

-- DuckDB: data/gamma_tool_sam.duckdb
CREATE TABLE positions (
    strike INTEGER PRIMARY KEY,
    net_contracts INTEGER,
    net_gamma REAL,
    total_gamma_force REAL,
    direction TEXT
);

CREATE TABLE alerts (
    id INTEGER PRIMARY KEY,
    timestamp TEXT,
    type TEXT,
    severity TEXT,
    strike INTEGER,
    details TEXT
);
```

### 6. The AsyncIO Queue Fix

**Problem**: Dealer engine wasn't receiving trades from the queue
**Root Cause**: `asyncio.Queue` created at module import time (before event loop exists)
**Solution**: Lazy initialization pattern in `shared_queue.py`

```python
# shared_queue.py
_TRADE_QUEUE = None

def get_trade_queue():
    global _TRADE_QUEUE
    if _TRADE_QUEUE is None:
        _TRADE_QUEUE = asyncio.Queue()  # Creates in correct event loop
    return _TRADE_QUEUE
```

### 7. Test Suite Organization

```
tests/
├── Core Tests (Always Run):
│   ├── test_snapshot.py         # Snapshot system functionality
│   ├── test_dealer_gamma.py     # Gamma calculations
│   ├── test_ws_client.py        # WebSocket connectivity
│   └── test_engine.py           # Dealer engine logic
│
├── Data Quality Tests:
│   ├── test_data_quality.py     # Data validation
│   ├── test_required_columns.py # Column presence
│   ├── test_bid_ask_not_null.py # NBBO validation
│   └── test_snapshot_file_exists.py # File system
│
├── Greek Calculation Tests:
│   ├── test_greeks_values.py    # Greek formulas
│   ├── test_surface.py          # Vol surface
│   └── test_gamma_not_null.py   # Gamma validation
│
└── Integration Tests:
    ├── test_trade_feed.py       # Trade processing
    ├── test_quote_cache.py      # Quote updates
    └── test_live_gamma_exists.py # Live gamma DB
```

### 8. System Verification Commands

```bash
# Check if system is running
ps aux | grep "python -m src.cli live"

# View current dealer gamma
python test_live_gamma.py

# Check latest snapshot
python check_snapshot_gamma.py

# Monitor live logs
tail -f /Users/michael/logs/live.out | grep -a engine

# Full system status
python system_status.py

# Watch snapshots being created
python watch_snapshots.py

# Run core test suite
python run_core_tests.py

# Quick pytest
./pytest.sh

# Check database directly
python -c "from src.persistence import get_latest_gamma; print(get_latest_gamma())"
```

### 9. Current System Results

✅ **Working Components:**
- Snapshot system creates files every 60s with full Greeks
- WebSocket streams quotes + trades successfully  
- Trade classification (BUY/SELL) working
- Gamma calculation per trade functioning
- Dealer position tracking operational
- Database persistence working
- **Latest Result: Dealer Gamma = -26.86** (4,065 trades processed)

🔧 **Integration Points:**
- Gamma Tool Sam dashboard needs connection fixes
- Dashboard should run on port 8080
- SPX price updates need to flow to all components
- Position tracking between systems needs sync