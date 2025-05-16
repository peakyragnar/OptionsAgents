"""
Test the Greek calculations in the snapshot module.
"""
import pytest
import pandas as pd
import numpy as np
import datetime
import sys
import os
from unittest import mock

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.utils.greeks import bs_greeks, implied_vol


def test_greeks_calculation():
    """Test the calculation of Greeks using our updated functions."""
    # Test ATM call option
    gamma, vega, theta = bs_greeks(100, 100, 0.2, 0.05, "C")
    assert gamma > 0, "Gamma should be positive"
    assert gamma < 1, "Gamma should be small for 5% DTE option"
    
    # Test higher gamma for shorter expiry
    gamma_short, _, _ = bs_greeks(100, 100, 0.2, 0.01, "C")
    assert gamma_short > gamma, "Gamma should be higher for shorter expiry"
    
    # Test put-call parity for gamma
    gamma_put, _, _ = bs_greeks(100, 100, 0.2, 0.05, "P")
    assert abs(gamma - gamma_put) < 1e-10, "Gamma should be the same for calls and puts"


def test_implied_vol_calculation():
    """Test the calculation of implied volatility."""
    # Create a price using known volatility
    s = 100
    k = 100
    true_vol = 0.2
    tau = 0.05  # ~2 weeks
    
    # Calculate option price with this volatility
    from scipy.stats import norm
    d1 = (np.log(s / k) + 0.5 * true_vol**2 * tau) / (true_vol * np.sqrt(tau))
    d2 = d1 - true_vol * np.sqrt(tau)
    call_price = s * norm.cdf(d1) - k * norm.cdf(d2)
    
    # Now try to recover volatility from price
    iv = implied_vol(call_price, s, k, tau, "C")
    assert iv is not None, "Implied volatility calculation should succeed"
    assert abs(iv - true_vol) < 0.001, "Implied volatility should match true volatility"


if __name__ == "__main__":
    test_greeks_calculation()
    test_implied_vol_calculation()
    print("All tests passed!")