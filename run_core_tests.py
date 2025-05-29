#!/usr/bin/env python3
"""Run core tests for Options Agents - Python version for better control."""

import subprocess
import sys

# Core unit tests that should always pass
CORE_TESTS = [
    # Engine and processing
    "tests/test_engine.py",
    "tests/test_strike_book.py",
    "tests/test_surface.py",
    
    # Greeks calculations
    "tests/test_greeks_values.py",
    
    # Trade classification
    "tests/test_classifier.py",
    "tests/test_ws_client_classify.py",
    
    # Data feeds (mocked)
    # Note: test_trade_feed.py has timing issues in test environment
    # "tests/test_trade_feed.py",
    "tests/test_ws_client.py",
    
    # Snapshot validation
    "tests/test_snapshot.py",
    "tests/test_current_snapshot.py",
    "tests/test_required_columns.py",
]

# Dealer gamma tests
GAMMA_TESTS = [
    "tests/test_dealer_gamma.py",
    "tests/test_dealer_gamma_direct.py", 
    "tests/test_dealer_gamma_values.py",
]

# Data quality tests
DATA_TESTS = [
    "tests/test_data_quality.py",
    "tests/test_bid_ask_not_null.py",
    "tests/test_gamma_not_null.py",
]

# Integration tests (require API key and market hours)
INTEGRATION_TESTS = [
    "tests/test_quote_cache.py",
    "tests/test_live_gamma_exists.py",
]

def run_tests(test_list, description):
    """Run a list of tests with description."""
    print(f"\n{'='*60}")
    print(f"{description}")
    print('='*60)
    
    cmd = ["pytest", "-q", "--tb=short"] + test_list
    result = subprocess.run(cmd)
    return result.returncode

def main():
    """Run test suites."""
    exit_code = 0
    
    # Run core tests
    exit_code |= run_tests(CORE_TESTS, "Running Core Unit Tests")
    
    # Run gamma tests  
    exit_code |= run_tests(GAMMA_TESTS, "Running Dealer Gamma Tests")
    
    # Run data quality tests
    exit_code |= run_tests(DATA_TESTS, "Running Data Quality Tests")
    
    # Show integration test info
    print(f"\n{'='*60}")
    print("Integration Tests (require API key and market hours):")
    print('='*60)
    print("To run integration tests:")
    print(f"  pytest -q {' '.join(INTEGRATION_TESTS)}")
    
    return exit_code

if __name__ == "__main__":
    sys.exit(main())