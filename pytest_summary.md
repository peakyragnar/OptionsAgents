# Pytest Summary for Options Agents

## Quick Test (All Pass) ✅
```bash
./pytest.sh
# Result: 2743 passed, 5 skipped
```

## Full Test Suite
```bash
python run_core_tests.py
# Note: May show 1-2 failures due to timing issues
```

## Test Categories

### ✅ Core Tests (Always Pass)
- `test_strike_book.py` - Strike book position tracking
- `test_surface.py` - Volatility surface caching
- `test_classifier.py` - Trade classification logic
- `test_ws_client_classify.py` - WebSocket classification
- `test_greeks_values.py` - Greeks calculations

### ✅ Snapshot Tests (Updated for 0DTE)
- `test_snapshot.py` - Validates 0DTE snapshot format (100-500 strikes)
- `test_current_snapshot.py` - Current snapshot validation
- `test_required_columns.py` - Schema validation

### ✅ Data Quality Tests (Handle Edge Cases)
- `test_data_quality.py` - Skips if all OI is zero (pre-market)
- `test_bid_ask_not_null.py` - Handles corrupted files gracefully
- `test_gamma_not_null.py` - Validates gamma calculations

### ⚠️ Tests Requiring Mocking
- `test_engine.py` - Needs POLYGON_KEY env var
- `test_trade_feed.py` - WebSocket mocking
- `test_ws_client.py` - WebSocket functionality

### 🔌 Integration Tests (Need API Key)
- `test_quote_cache.py` - Requires live Polygon connection
- `test_live_gamma_exists.py` - Requires market hours

## Known Issues Fixed

1. **Strike Count**: 0DTE options have ~270 strikes, not 450+
2. **Open Interest**: Pre-market snapshots have zero OI
3. **ZSTD Errors**: Some old parquet files are corrupted
4. **Async Tests**: Added pytest-asyncio support

## Environment Setup

The `conftest.py` file sets default test environment variables:
- `POLYGON_KEY=TEST_KEY`
- `OA_GAMMA_DB=test.db`

## Run Specific Tests

```bash
# Just gamma tests
pytest -q tests/test_dealer_gamma*.py

# Skip slow tests
pytest -q -m "not slow"

# With coverage
pytest --cov=src tests/
```