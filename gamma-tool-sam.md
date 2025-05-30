# Gamma Tool Sam - Real-Time 0DTE Directional Gamma Analysis

## Overview

Gamma Tool Sam is a real-time directional gamma analysis system designed for 0DTE SPX options trading. Created based on Sam's methodology, it tracks institutional option selling activity to identify intraday pinning levels and directional market forces.

### Core Assumptions
- 0DTE option sellers are primarily large institutions (Citadel, market makers)
- These institutions are net sellers (rarely buy back intraday)
- All trade volume represents institutional selling activity
- Dealer hedging of short gamma positions creates directional market forces
- All trades are meaningful (no filtering of penny trades - they may represent end-of-day positioning)

## Architecture

### 1. Data Flow Pipeline

```
WebSocket Trade Feed → Trade Processor → Gamma Calculator → Change Detector → Output Layer
                           ↓                    ↓                ↓
                      Quote Cache          Position Tracker   Database
                        (NBBO)              (By Strike)      (Historical)
```

### 2. Dual-Purpose Design

#### Human Interface (Manual Trading)
- Real-time dashboard with visual indicators
- Clear directional signals and price targets
- Change alerts with priority levels
- Non-blocking display (web or terminal-based)

#### Agent Interface (Automated Trading)
- RESTful API endpoints
- Structured JSON responses
- Event-driven webhooks for alerts
- Backtesting data access

## Core Components

### 1. Trade Processor (`trade_processor.py`)
- Receives ALL SPX 0DTE option trades (no filtering)
- Extracts strike, type (call/put), size, price
- Timestamps and stores every trade for analysis
- Maintains real-time position tracking

### 2. Gamma Calculator (`gamma_calculator.py`)
- Calculates Black-Scholes gamma for each trade
- Determines directional force:
  - Calls above SPX = Upward force
  - Puts below SPX = Downward force
  - ATM options = Neutral force
- Aggregates total gamma by strike
- Computes net directional pressure

### 3. Change Detector (`change_detector.py`)
- Multi-timeframe analysis (1min, 5min, 15min)
- Spike detection (volume/gamma surges)
- Momentum tracking (acceleration/deceleration)
- Direction flip identification
- New pin formation alerts

### 4. Position Tracker (`position_tracker.py`)
- Maintains dealer short positions by strike
- Tracks cumulative gamma exposure
- Updates with each trade
- Provides position snapshots for analysis

### 5. Output Layer (`output_handler.py`)
- Human dashboard formatting
- Agent API responses
- Alert prioritization
- Signal generation

## Database Architecture

### Storage Strategy
Gamma Tool Sam uses DuckDB for real-time analytics and Parquet files for historical data, maintaining consistency with the existing OptionsAgents system.

```
Trade Feed → In-Memory Calculations → DuckDB (live) → Parquet (archive)
```

### DuckDB Schema (Real-time Operations)

```sql
-- Live gamma positions (updates with each trade)
CREATE TABLE gamma_positions_live (
    timestamp TIMESTAMP,
    strike INTEGER,
    option_type VARCHAR(4),  -- 'CALL' or 'PUT'
    cumulative_volume INTEGER,  -- Total contracts sold at this strike
    gamma_per_contract REAL,
    total_gamma REAL,  -- gamma_per_contract * cumulative_volume
    directional_force VARCHAR(10),  -- 'UPWARD', 'DOWNWARD', 'NEUTRAL'
    spx_price REAL,
    PRIMARY KEY (strike, option_type)
);

-- Rolling window for change detection (1-min buckets)
CREATE TABLE gamma_changes_1min (
    timestamp TIMESTAMP,
    strike INTEGER,
    volume_spike INTEGER,  -- Contracts traded in this minute
    gamma_added REAL,
    alert_type VARCHAR(20),  -- 'SPIKE', 'NEW_PIN', 'DIRECTION_FLIP'
    details VARCHAR  -- JSON string with additional context
);

-- Current analysis state
CREATE TABLE gamma_analysis_current (
    timestamp TIMESTAMP,
    net_force REAL,
    primary_pin INTEGER,
    direction VARCHAR(10),
    confidence REAL,
    top_strikes VARCHAR,  -- JSON array of top pins
    active_alerts VARCHAR  -- JSON array of current alerts
);
```

### Parquet Archive Structure

```
data/gamma_tool_sam/
├── positions/
│   └── date=2025-01-30/
│       ├── 09_35_00.parquet  # 5-minute position snapshots
│       ├── 09_40_00.parquet
│       └── ...
├── trades/
│   └── date=2025-01-30/
│       └── trades.parquet    # All trades for backtesting
└── analysis/
    └── date=2025-01-30/
        └── summary.parquet   # End-of-day analysis
```

### Data Lifecycle

- **LIVE (< 1 hour)**: DuckDB tables for sub-second queries
- **RECENT (today)**: DuckDB + Parquet for dual access
- **HISTORICAL (> 1 day)**: Parquet only for efficient storage

## Output Specifications

### Human Dashboard

```
GAMMA TOOL SAM | SPX: $5,905.25 | 10:45:32
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

DIRECTIONAL FORCE: +485K ↑ UPWARD
Primary Target: 5910 (5pts away)
Confidence: ████████░░ 82%

TOP PINS:
↑ 5910: ████████ 850K
↑ 5920: █████ 520K  
↓ 5895: ████ 365K

⚡ ALERTS (Last 5min):
• SPIKE: 200x 5910C @ 10:43 (+150K)
• NEW PIN: 5920 growing rapidly
• MOMENTUM: Accelerating upward

SIGNAL: LONG → 5910 | Stop: 5900
```

### Agent API Endpoints

```python
GET /api/gamma/summary
Response: {
    "timestamp": "2024-01-30T10:45:32",
    "spx_price": 5905.25,
    "net_force": 485000,
    "direction": "UP",
    "confidence": 0.82,
    "primary_pin": {"strike": 5910, "force": 850000},
    "signal": {"action": "LONG", "target": 5910, "stop": 5900}
}

GET /api/gamma/changes?timeframe=5m
Response: {
    "changes": [
        {"type": "SPIKE", "strike": 5910, "magnitude": 3.2},
        {"type": "NEW_PIN", "strike": 5920, "growth": 0.8}
    ]
}

GET /api/gamma/strikes
Response: {
    "strikes": {
        "5910": {"gamma": 850000, "direction": "UP", "position": -2500},
        "5895": {"gamma": 365000, "direction": "DOWN", "position": -1200}
    }
}

POST /api/gamma/subscribe
Body: {"events": ["SPIKE", "DIRECTION_FLIP"], "webhook": "https://..."}
```

## Implementation Phases

### Phase 1: Core System (Day 1 - Before Market Open)
1. Set up trade processor with WebSocket integration
2. Implement gamma calculations with directional logic
3. Create position tracking system
4. Build basic change detection
5. Test with historical data

### Phase 2: Change Detection (Day 1 - Market Hours)
1. Implement multi-timeframe analysis
2. Add spike detection algorithms
3. Create momentum tracking
4. Build alert system
5. Live testing and tuning

### Phase 3: Output Layer (Day 2)
1. Build human dashboard (web-based)
2. Create agent API endpoints
3. Implement database persistence
4. Add real-time updates
5. Create signal generation logic

### Phase 4: Advanced Features (Week 1)
1. Enhanced change detection patterns
2. Machine learning for spike prediction
3. Backtesting framework
4. Performance analytics
5. Risk management layers

## Usage Examples

### Manual Trading
```bash
# Start the system
python -m gamma_tool_sam.run

# Opens web dashboard at http://localhost:8080
# Shows real-time gamma analysis with trading signals
```

### Agent Integration
```python
from gamma_tool_sam import GammaClient

client = GammaClient()

# Get current analysis
analysis = client.get_summary()
if analysis['confidence'] > 0.8:
    if analysis['direction'] == 'UP':
        place_long_order(target=analysis['primary_pin']['strike'])

# Subscribe to alerts
client.subscribe(events=['SPIKE', 'DIRECTION_FLIP'], 
                callback=handle_gamma_event)
```

## Performance Requirements

- Process trades within 100ms of receipt
- Update calculations in real-time
- Dashboard refresh every 1 second
- API response time < 50ms
- Handle 1000+ trades per minute

## Risk Considerations

1. **Data Quality**: Depends on accurate real-time trade feed
2. **Assumptions**: Based on institutional selling behavior
3. **Market Conditions**: Best in normal volatility environments
4. **Technology**: Requires stable WebSocket connections
5. **Latency**: Every millisecond matters for signals

## Success Metrics

- Accurate prediction of intraday pin levels
- Early detection of directional changes
- Profitable signal generation
- Low false positive rate on alerts
- Smooth transition to agent automation

## Future Enhancements

1. Multi-strike correlation analysis
2. Volume-weighted gamma calculations
3. Integration with other market indicators
4. Advanced ML for pattern recognition
5. Automated strategy execution