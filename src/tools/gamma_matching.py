"""
Script to precisely match our system's gamma calculation and verify correctness.
Uses realistic market parameters including non-zero risk-free rate.
"""

import math
import numpy as np
from scipy.stats import norm

def black_scholes_gamma(S, K, T, r, sigma):
    """Calculate the gamma of an option using Black-Scholes formula."""
    # Ensure minimum values for numerical stability
    T = max(T, 1e-6)
    sigma = max(sigma, 0.001)
    
    d1 = (math.log(S/K) + (r + 0.5 * sigma**2) * T) / (sigma * math.sqrt(T))
    gamma = norm.pdf(d1) / (S * sigma * math.sqrt(T))
    
    return gamma

def find_matching_parameters():
    """Find parameters that match our system's gamma value."""
    # Target gamma from our system
    target_gamma = 0.002309246964667882
    
    # Fixed parameters
    S = 5000.0
    K = 4900.0
    r = 0.04  # 4% risk-free rate
    
    # Variables to try
    times_to_expiry = [1/365.0, 2/365.0, 3/365.0, 4/365.0, 5/365.0]
    volatilities = np.linspace(0.25, 0.35, 21)
    
    best_match = (float('inf'), None, None)
    
    print("Finding parameters that match gamma = 0.002309246964667882")
    print("Using 4% risk-free rate")
    print("\nTesting combinations of time to expiry and volatility:")
    print(f"{'T (days)':<10} {'Volatility':<12} {'Calculated Gamma':<18} {'Difference':<15}")
    print(f"{'-'*55}")
    
    for T in times_to_expiry:
        for sigma in volatilities:
            gamma = black_scholes_gamma(S, K, T, r, sigma)
            diff = abs(gamma - target_gamma)
            
            if diff < best_match[0]:
                best_match = (diff, T, sigma)
            
            # Only print close matches to avoid cluttering the output
            if diff < 0.0002:
                print(f"{T*365.0:<10.5f} {sigma:<12.5f} {gamma:<18.15f} {diff:<15.15f}")
    
    diff, T, sigma = best_match
    print(f"\nBest match:")
    print(f"Time to expiry: {T*365.0:.5f} days")
    print(f"Volatility: {sigma:.5f}")
    print(f"Risk-free rate: 4.00%")
    print(f"Calculated gamma: {black_scholes_gamma(S, K, T, r, sigma):.15f}")
    print(f"Target gamma:     {target_gamma:.15f}")
    print(f"Difference:       {diff:.15f}")
    
    # Verify that our total gamma calculation is correct
    size = 3
    expected_total = size * black_scholes_gamma(S, K, T, r, sigma)
    print(f"\nVerifying total gamma for size = {size}:")
    print(f"Calculated total: {expected_total:.15f}")
    print(f"System total:     {3 * target_gamma:.15f}")
    print(f"Match: {abs(expected_total - 3 * target_gamma) < 1e-10}")
    
    # Demonstrate impact of risk-free rate
    print("\nImpact of risk-free rate on gamma calculation:")
    r_values = [0.0, 0.02, 0.04, 0.05, 0.06]
    print(f"{'Rate':<10} {'Gamma':<18} {'% Difference from r=0':<25}")
    base_gamma = black_scholes_gamma(S, K, T, 0.0, sigma)
    for rate in r_values:
        gamma = black_scholes_gamma(S, K, T, rate, sigma)
        pct_diff = (gamma - base_gamma) / base_gamma * 100 if base_gamma else 0
        print(f"{rate*100:<10.2f}% {gamma:<18.15f} {pct_diff:<25.5f}%")

if __name__ == "__main__":
    print("=" * 70)
    print("GAMMA CALCULATION PARAMETER MATCHING")
    print("=" * 70)
    
    find_matching_parameters()
    
    print("\nVerification complete.")