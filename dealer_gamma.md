# 0DTE Dealer Gamma Pin Detection Strategy

## Overview

This document explains our 0DTE (zero days to expiration) options trading strategy that leverages dealer gamma positioning to identify and trade around "pinning" behavior in SPX options.

## The Core Strategy

### The Setup (Early Day)
- **Large 0DTE sellers** (Citadel-scale market makers) sell massive premium in SPX options
- **We follow along** - sell premium alongside these institutional players
- **Goal**: Collect premium as SPX gets "pinned" to high-volume strikes due to dealer hedging

### The Detection (Last 90 Minutes)
- **Volume analysis** - Identify where the big positions are concentrated
- **Pin expectation** - SPX should gravitate toward high gamma strikes
- **Risk monitoring** - If pin fails, big moves incoming (volatility expansion)

### Our Enhancement
Instead of just tracking volume, we calculate **actual gamma exposure by strike** to better predict pin strength and potential failure points.

## The Mathematics Behind Pin Detection

### Pin Force Calculation

For each strike, we calculate:
```
Net 0DTE Short Volume × Gamma Per Contract = Pin Force
```

#### Example:
- **5850 Strike**: 50,000 contracts short × 0.008 gamma = 400,000 "pin units"
- **5855 Strike**: 12,000 contracts short × 0.006 gamma = 72,000 "pin units"
- **Result**: Strong pin expected at 5850, weak at 5855

## Key Implementation Components

### 1. Volume-Based Position Estimation
- Track net premium selling volume by strike
- Assumption: High volume = large short positions
- Focus patterns:
  - Call selling above SPX (bearish premium collection)
  - Put selling below SPX (bullish premium collection)
  - ATM straddle/strangle selling (volatility selling)

### 2. Gamma Exposure Calculation
- Pull current gamma per contract from our snapshots
- Calculate total estimated short gamma by strike
- "Pin strength" = Volume × Gamma × 100 (shares per contract)

### 3. Real-Time Pin Monitoring
- Track where SPX is relative to max gamma strikes
- Measure "pin force" strength throughout the day
- Early warning system if pins start failing

## Implementation Architecture

### Phase 1: Volume-Based Gamma Estimation
```python
def calculate_pin_strength(strike_data, spx_level):
    pin_forces = {}
    
    for strike in strike_data:
        # Estimate net short positions from volume
        if strike > spx_level:
            # Calls above SPX - likely short call positions
            estimated_short = strike['call_volume'] * 0.6  # Assume 60% short
        else:
            # Puts below SPX - likely short put positions  
            estimated_short = strike['put_volume'] * 0.6
        
        # Calculate pin force
        gamma = strike['gamma_per_contract']
        pin_force = estimated_short * gamma * 100  # 100 shares per contract
        pin_forces[strike] = pin_force
    
    return pin_forces
```

### Phase 2: Real-Time Analysis
- Process each trade through WebSocket feed
- Update cumulative positions continuously
- Detect volume spikes (5-minute rolling window)
- Alert on significant gamma exposure changes

### Phase 3: Enhanced Trade Classification
- Leverage our proven NBBO-based trade classification
- Identify premium selling vs buying patterns
- Weight analysis by trade size and timing

## System Design Decisions

### 1. Volume Tracking Strategy
- **Cumulative Volume**: Track total positions built throughout the day
- **Spike Detection**: Monitor recent flow (last 5 minutes) for sudden changes
- **Dual Approach**: Weight both for comprehensive analysis

### 2. Strike Selection
- **Primary Focus**: ±75 strikes around current SPX (captures 99% of 0DTE activity)
- **Full Chain Support**: System handles entire chain for completeness
- **Dynamic Adjustment**: Focus zone moves with SPX throughout the day

### 3. Timing & Storage
- **Real-Time Processing**: Every trade updates the analysis
- **Snapshot Integration**: Hourly gamma surface updates from snapshots
- **Backtesting Storage**: All data stored in DuckDB for historical analysis

## Trading the Pin

### Entry Signals
1. **Strong Pin Identified**: Large gamma concentration at specific strike
2. **SPX Approaching Pin**: Price movement toward high gamma strike
3. **Volume Confirmation**: Continued premium selling at pin level

### Trade Types
- **Pin Plays**: Sell premium expecting SPX to pin
- **Pin Break Plays**: Buy premium when pins fail (volatility expansion)
- **Butterfly Spreads**: Center around expected pin strikes

### Risk Management
- **Pin Failure**: Monitor for volume/price divergence
- **Time Decay**: 0DTE theta accelerates in final hours
- **Gamma Risk**: Understand explosion risk near pins

## Technical Integration

### Data Flow
1. **Polygon WebSocket** → Real-time trades
2. **Trade Classifier** → Identify buyer/seller
3. **Pin Detector** → Calculate gamma exposure
4. **Risk Monitor** → Alert on changes

### Key Metrics Tracked
- Net short volume by strike
- Gamma exposure ($-terms)
- Pin force strength (volume × gamma)
- Volume spike alerts
- SPX distance to pins

## Backtesting Capabilities

The system stores:
- All trades with classifications
- Gamma surfaces throughout the day
- Pin predictions vs actual SPX movement
- P&L of various pin strategies

This enables analysis of:
- Pin success rates by market conditions
- Optimal entry/exit timing
- Risk/reward of different pin plays
- Market maker positioning patterns

## Future Enhancements

1. **Machine Learning**: Predict pin success probability
2. **Multi-Strike Analysis**: Identify pin "clusters"
3. **Greeks Integration**: Add vega for volatility analysis
4. **Automated Execution**: Trade pin setups automatically

## Summary

This 0DTE pin detection system leverages the market microstructure reality that large dealers must hedge their gamma exposure. By tracking where dealers are short gamma (through premium selling), we can identify price levels that act as "magnets" due to hedging flows. The system provides real-time analysis, spike detection, and historical storage for comprehensive pin trading strategies.