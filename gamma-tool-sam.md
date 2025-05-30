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

### 6. Confidence Calculator (`confidence_calculator.py`)
- Multi-factor confidence scoring system
- Market condition adaptation
- Pattern recognition and adjustments
- Transparent explanations for every score

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

## Sophisticated Confidence Calculation System

The confidence system provides nuanced, explainable confidence scores that adapt to market conditions and learn from patterns.

### Multi-Factor Confidence Model

The confidence score combines five weighted components:

#### 1. **Force Score (30% weight)**
- Measures the magnitude of net directional gamma force
- Normalized against dynamic thresholds that adjust for:
  - Time of day (morning = lower threshold, afternoon = higher)
  - Market volatility (high VIX = higher threshold needed)
  - Volume percentile (high volume = more significant moves)

#### 2. **Imbalance Score (25% weight)**
- Measures how one-sided the gamma positioning is
- Formula: `|upward_force - downward_force| / total_force`
- Higher imbalance = stronger directional conviction
- Balanced gamma (score near 0) indicates uncertainty

#### 3. **Concentration Score (20% weight)**
- Measures if gamma is concentrated at few strikes or spread out
- Calculates: top 3 strikes gamma / total gamma
- High concentration = clearer pin targets
- Dispersed gamma = less confident directional bias

#### 4. **Distance Score (15% weight)**
- Measures proximity of primary pin to current SPX price
- Closer pins have stronger magnetic effect
- Score decreases linearly: 50 points away = 0 confidence
- Formula: `max(0, 1 - (distance / 50))`

#### 5. **Momentum Score (10% weight)**
- Assesses if recent activity aligns with gamma direction
- Checks for momentum shifts in last 5 minutes
- Aligned momentum = 0.9 score
- Opposing momentum = 0.3 score
- Neutral = 0.6 score

### Pattern Recognition Adjustments

The system detects and adjusts confidence based on market patterns:

#### **Pin Sandwich** (+20% confidence)
- Strong pin with weaker pins on adjacent strikes
- Clear target with less competition
- Indicates focused dealer positioning

#### **Near Gamma Flip** (-20% confidence)
- Net force close to zero relative to total gamma
- Market at inflection point
- Direction could change quickly

#### **Competing Pins** (-30% confidence)
- Multiple strong pins within 30% strength of each other
- Conflicting forces reduce directional clarity
- Market may oscillate between levels

#### **Momentum Divergence** (-40% confidence)
- Recent direction flips detected
- Price action not aligned with gamma forces
- Indicates potential regime change

#### **Volume Surge** (+10% confidence)
- Multiple recent spikes (3+ in 5 minutes)
- Increased activity confirms positioning
- Higher conviction in gamma levels

### Gamma Quality Scoring

Not all gamma is equal. The system assesses quality based on:

#### **Volume Backed (40% weight)**
- Gamma from actual traded volume vs theoretical
- High volume = real positioning
- Low volume = potentially stale

#### **Recent (30% weight)**
- Gamma from trades in last 30 minutes
- Fresh positioning more relevant than old
- Decays over 2-hour window

#### **Institutional (20% weight)**
- Large block trades indicate institutional activity
- Average trade size > 100 contracts = institutional
- Small trades may be retail noise

#### **Persistent (10% weight)**
- Steady building vs sudden spikes
- Persistent growth = sustainable pin
- Spike-only = potentially temporary

### Market Condition Adaptations

#### **Time of Day Adjustments**
- **9:30-10:30 AM**: Lower thresholds (×0.8) - positioning period
- **10:30-3:30 PM**: Normal thresholds - steady trading
- **3:30-4:00 PM**: Higher thresholds (×1.5) - position squaring

#### **Volatility Adjustments**
- **VIX < 12**: Lower thresholds (×0.8) - calm markets
- **VIX 12-20**: Normal thresholds
- **VIX > 20**: Higher thresholds (×1.3) - need more conviction

#### **Volume Percentile Adjustments**
- **> 80th percentile**: Lower thresholds (×0.9) - significant day
- **20th-80th percentile**: Normal thresholds
- **< 20th percentile**: Higher thresholds (×1.2) - quiet day

### Confidence Interpretation

#### **80-100% Confidence**
- Strong directional signal
- Clear pin targets with aligned forces
- High conviction for directional trades
- Tight stops can be used

#### **60-80% Confidence**
- Moderate directional bias
- Some conflicting signals but net direction clear
- Normal position sizing appropriate
- Standard stops recommended

#### **40-60% Confidence**
- Weak directional signal
- Mixed forces or unclear patterns
- Reduced position size or avoid trading
- Wide stops if trading

#### **0-40% Confidence**
- No clear direction
- Conflicting forces or patterns
- Avoid directional trades
- Wait for clarity

### API Access to Confidence Details

```python
GET /api/confidence
Response: {
    "overall_confidence": 0.82,
    "components": {
        "force": {"score": 0.9, "weight": 0.30},
        "imbalance": {"score": 0.8, "weight": 0.25},
        "concentration": {"score": 0.75, "weight": 0.20},
        "distance": {"score": 0.7, "weight": 0.15},
        "momentum": {"score": 0.6, "weight": 0.10}
    },
    "patterns": ["pin_sandwich", "volume_surge"],
    "explanation": [
        "Strong directional gamma force",
        "Heavily one-sided gamma",
        "Clear pin formation with weak neighbors",
        "HIGH CONFIDENCE setup"
    ],
    "market_conditions": {
        "time": "10:45",
        "vix": 15.0,
        "volume_percentile": 65
    },
    "adjustments": {
        "base": 0.76,
        "pattern_adjusted": 0.82,
        "quality_adjusted": 0.82,
        "final": 0.82
    }
}
```

### Self-Learning Capability

The system includes a `record_outcome()` method to track prediction accuracy:

```python
# After market close, record if prediction was correct
confidence_calculator.record_outcome({
    'confidence': 0.82,
    'direction': 'UP',
    'patterns': ['pin_sandwich'],
    'outcome': 'correct'  # or 'incorrect'
})
```

Over time, this allows the system to:
- Calibrate confidence scores to actual success rates
- Identify which patterns are most predictive
- Adjust component weights based on performance
- Improve accuracy through experience

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

## Dynamic Gamma Thresholds

Gamma Tool Sam uses dynamic thresholds that adjust throughout the trading day to account for natural market rhythms:

### Time-Based Thresholds
- **9:30-10:00 AM**: 25K threshold - Morning positioning period, high sensitivity
- **10:00-11:00 AM**: 75K threshold - Positions building, moderate sensitivity  
- **11:00-2:00 PM**: 150K threshold - Peak trading hours, normal sensitivity
- **2:00-3:30 PM**: 250K threshold - Heavy positioning, reduced sensitivity
- **3:30-4:00 PM**: 400K threshold - End of day, only massive gamma matters

### Premium Selling Strategies

When gamma is below the dynamic threshold, the system identifies premium selling opportunities:

#### **SELL_STRADDLE** (Net gamma < 10K)
- Extremely low gamma indicates minimal movement expected
- Sell ATM straddle at nearest strike
- Manage at identified range boundaries
- Highest risk/reward for quiet markets

#### **SELL_IRON_CONDOR** (Range width ≤ 20 points, gamma < 50K)  
- Tight range between upward and downward pins
- Sell wings outside the pin range (5 points buffer)
- Lower risk than straddle with defined max loss
- Ideal for range-bound markets

#### **SELL_BUTTERFLY** (Near strong pin, distance < 10 points)
- Pin magnetism expected to hold price
- Center butterfly on the pin strike
- 10-point wings for risk management
- Best for pin-to-pin movement expectations

### Signal Confidence Adjustments

Confidence scores now use dynamic thresholds:
- Force relative to time-appropriate threshold
- Morning setups need less absolute gamma
- Afternoon setups need more conviction
- End-of-day requires extreme positioning

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
- Dynamic threshold calculation < 10ms
- Premium strategy evaluation < 20ms

## Risk Considerations

1. **Data Quality**: Depends on accurate real-time trade feed
2. **Assumptions**: Based on institutional selling behavior
3. **Market Conditions**: Best in normal volatility environments
4. **Technology**: Requires stable WebSocket connections
5. **Latency**: Every millisecond matters for signals
6. **Dynamic Thresholds**: Time-based adjustments may need calibration
7. **Premium Selling**: Requires careful risk management and position sizing

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