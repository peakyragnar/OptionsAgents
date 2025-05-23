# OptionsAgents Test Suite Validation Plan

## Overview
Systematic testing plan for 0DTE SPX options trading system while market is closed.

---

## 1. Core Components Test Structure

### **A. Data Ingestion Tests (`/tests/test_ingest/`)**
```
test_snapshot.py          # SPX options chain capture
test_quote_cache.py       # NBBO quote management  
test_trade_feed.py        # Polygon.io WebSocket connectivity
test_persistence.py       # Parquet/DuckDB storage
```

### **B. Options Greeks Tests (`/tests/test_greeks/`)**
```
test_black_scholes.py     # Greeks calculations
test_implied_vol.py       # Volatility calculations
test_0dte_gamma.py        # Extreme gamma scenarios
test_edge_cases.py        # Near-expiry boundary conditions
```

### **C. Dealer Engine Tests (`/tests/test_dealer/`)**
```
test_trade_classification.py  # Buy/sell classification
test_position_tracking.py     # Strike-level position management
test_gamma_exposure.py        # Net gamma calculations
test_flow_balance.py          # Customer flow analysis
```

### **D. Integration Tests (`/tests/test_integration/`)**
```
test_end_to_end.py        # Full pipeline testing
test_data_consistency.py  # Cross-component validation
test_performance.py       # Latency and throughput
```

---

## 2. Critical Test Cases for 0DTE SPX

### **🚨 High Priority - Data Integrity**

**Test 1: Options Chain Snapshot Validation**
```python
def test_spx_options_chain_structure():
    """Verify SPX options chain has correct 0DTE structure"""
    # Test for proper strike spacing
    # Verify expiration date handling
    # Check for missing strikes near ATM
    # Validate bid/ask spread reasonableness
```

**Test 2: NBBO Quote Cache Accuracy**
```python
def test_nbbo_quote_freshness():
    """Ensure quotes are current and properly formatted"""
    # Test timestamp validation
    # Check for stale quotes
    # Verify bid < ask constraint
    # Test quote update frequency
```

**Test 3: Trade Classification Logic**
```python
def test_trade_classification_accuracy():
    """Critical for dealer gamma calculations"""
    # Test buy vs sell classification using NBBO
    # Verify customer vs market maker identification
    # Test edge cases (trades at mid, wide spreads)
    # Validate classification confidence scores
```

### **⚡ Critical - Dealer Gamma Calculations**

**Test 4: Net Position Calculation**
```python
def test_dealer_net_positioning():
    """Fix the core dealer gamma issue"""
    # Test: (Customer Buys - Customer Sells) = Dealer Net Short
    # Verify proper netting across all strikes
    # Test position rollup accuracy
    # Validate gamma exposure calculation
```

**Test 5: Flow Balance Analysis**
```python
def test_customer_flow_balance():
    """Verify balanced vs imbalanced flow detection"""
    # Test scenario: 50k buys + 50k sells = 0 net exposure
    # Test scenario: 100k buys + 20k sells = significant exposure
    # Verify proper aggregation across strikes
    # Test gamma wall detection logic
```

**Test 6: 0DTE Gamma Sensitivity**
```python
def test_extreme_gamma_scenarios():
    """Handle extreme 0DTE gamma values"""
    # Test gamma calculations near expiration
    # Verify handling of deep ITM/OTM options
    # Test gamma explosion scenarios
    # Validate numerical stability
```

### **📊 Data Persistence & Retrieval**

**Test 7: DuckDB Storage Validation**
```python
def test_duckdb_gamma_snapshots():
    """Verify gamma snapshot storage integrity"""
    # Test proper schema creation
    # Verify data type handling
    # Test query performance
    # Validate historical data consistency
```

**Test 8: Parquet File Structure**
```python
def test_parquet_options_chain():
    """Verify efficient storage of options data"""
    # Test partitioning by date
    # Verify compression efficiency
    # Test read performance
    # Validate schema evolution
```

---

## 3. Mock Data for Testing

### **Sample 0DTE SPX Data Structure**
```python
MOCK_0DTE_SPX_OPTION = {
    "symbol": "SPXW240523C05200000",  # 0DTE call
    "strike": 5200.0,
    "expiry": "2024-05-23",
    "option_type": "C",
    "bid": 15.50,
    "ask": 16.00,
    "last": 15.75,
    "volume": 1250,
    "open_interest": 0,  # 0DTE typically has low OI
    "implied_vol": 0.35,
    "delta": 0.45,
    "gamma": 0.0012,  # High for 0DTE
    "theta": -0.85,   # Extreme time decay
    "vega": 2.1
}
```

### **Sample Trade Data**
```python
MOCK_TRADE = {
    "symbol": "SPXW240523C05200000",
    "price": 15.75,
    "size": 10,
    "timestamp": "2024-05-23T14:30:00.123Z",
    "exchange": "CBOE",
    "conditions": ["Regular Sale"],
    "nbbo_bid": 15.50,
    "nbbo_ask": 16.00
}
```

---

## 4. Test Execution Strategy

### **Phase 1: Unit Tests (Run First)**
1. Test individual components in isolation
2. Verify basic functionality and edge cases
3. Validate mathematical calculations

### **Phase 2: Integration Tests**
1. Test component interactions
2. Verify data flow between modules
3. Test error handling and recovery

### **Phase 3: End-to-End Validation**
1. Run full pipeline with mock data
2. Verify output accuracy and consistency
3. Test performance under load

### **Phase 4: Historical Data Replay**
1. Use recorded 0DTE SPX data
2. Validate dealer gamma calculations
3. Compare against known market events

---

## 5. Known Issues to Test For

### **🔧 Potential Dealer Gamma Calculation Bugs**
- **Net Position Error**: Not properly netting customer buys vs sells
- **Strike Aggregation**: Incorrect rollup across strikes
- **Time Decay Handling**: Not accounting for 0DTE theta explosion
- **Gamma Scaling**: Incorrect position size to gamma exposure conversion

### **🔧 Data Quality Issues**
- **Stale Quotes**: Using outdated NBBO data for classification
- **Missing Strikes**: Gaps in options chain around ATM
- **Trade Duplicates**: Double-counting trades from multiple feeds
- **Timestamp Sync**: Misaligned data across components

---

## 6. Test Commands to Run

```bash
# Run specific test categories
pytest tests/test_greeks/ -v                    # Greeks calculations
pytest tests/test_dealer/ -v                    # Dealer engine tests
pytest tests/test_ingest/ -v                    # Data ingestion
pytest tests/test_integration/ -v               # End-to-end tests

# Run with coverage
pytest --cov=src tests/ --cov-report=html

# Run performance tests
pytest tests/test_performance.py -v --benchmark-only

# Run with detailed output
pytest -v -s tests/
```

---

## 7. Success Criteria

✅ **All unit tests pass with >95% code coverage**  
✅ **Dealer gamma calculations match theoretical values**  
✅ **Trade classification accuracy >98%**  
✅ **Data persistence with zero data loss**  
✅ **End-to-end pipeline runs without errors**  
✅ **Performance meets latency requirements (<100ms)**

---

## Next Steps

1. **Run existing tests** to identify current failures
2. **Fix dealer gamma calculation logic** based on test results
3. **Add missing test cases** for 0DTE-specific scenarios
4. **Validate with historical data** replay
5. **Performance optimization** based on test results