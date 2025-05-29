#!/bin/bash
# Run core tests for Options Agents

# Set dummy environment variables for tests if not already set
export POLYGON_KEY="${POLYGON_KEY:-TEST_KEY}"
export OA_GAMMA_DB="${OA_GAMMA_DB:-test.db}"

echo "Running core unit tests..."
pytest -q tests/test_engine.py \
       tests/test_strike_book.py \
       tests/test_surface.py \
       tests/test_greeks_values.py \
       tests/test_classifier.py \
       tests/test_trade_feed.py \
       tests/test_ws_client.py \
       tests/test_ws_client_classify.py \
       tests/test_current_snapshot.py

echo -e "\n\nRunning dealer gamma tests..."
pytest -q tests/test_dealer_gamma.py \
       tests/test_dealer_gamma_direct.py \
       tests/test_dealer_gamma_values.py

echo -e "\n\nTo run integration tests (requires API key and market hours):"
echo "pytest -q tests/test_quote_cache.py tests/test_live_gamma_exists.py"