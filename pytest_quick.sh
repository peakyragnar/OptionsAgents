#!/bin/bash
# Quick pytest run for core functionality

echo "Running core tests that should always pass..."
pytest -q --tb=short \
  tests/test_strike_book.py \
  tests/test_surface.py \
  tests/test_classifier.py \
  tests/test_ws_client_classify.py \
  tests/test_greeks_values.py \
  tests/test_snapshot.py::test_snapshot_file_basic \
  -k "not test_quote_cache"

echo -e "\n\nFor full test suite: python run_core_tests.py"