"""
Option Greeks calculation utilities using Black-Scholes model.
Includes functions for calculating implied volatility and option Greeks.
"""
import math
from scipy import stats, optimize


def implied_vol(option_type, S, K, T, r, price, precision=0.00001, max_iterations=100):
    """
    Calculate implied volatility using Brent's method.
    
    Parameters:
    option_type: 'call' or 'put'
    S: spot price (current underlying price)
    K: strike price
    T: time to maturity in years (e.g., 5/365 for 5 days)
    r: risk-free rate (e.g., 0.05 for 5%)
    price: market price of the option
    precision: precision for the implied volatility calculation
    max_iterations: maximum number of iterations for Brent's method
    
    Returns:
    Implied volatility as a float or None if calculation fails
    """
    # Ensure minimum time to maturity to avoid numerical issues
    T = max(T, 1/365)
    
    # Set bounds for implied volatility
    iv_min = 0.001
    iv_max = 5.0  # 500% volatility is a reasonable upper bound
    
    # Define objective function (difference between theoretical and market price)
    def objective(sigma):
        try:
            price_theoretical = bs_price(option_type, S, K, T, r, sigma)
            return price_theoretical - price
        except (ValueError, OverflowError):
            # Return a large number if calculation fails
            return 1000.0
            
    try:
        # Use Brent's method to find the implied volatility
        iv = optimize.brentq(
            objective, iv_min, iv_max,
            rtol=precision,
            maxiter=max_iterations
        )
        return iv
    except (ValueError, RuntimeError):
        # If Brent's method fails, return None
        return None


def bs_price(option_type, S, K, T, r, sigma):
    """
    Calculate option price using Black-Scholes formula.
    """
    # Ensure minimum time to maturity to avoid numerical issues
    T = max(T, 1/365)
    
    # Calculate d1 and d2
    d1 = (math.log(S/K) + (r + 0.5 * sigma**2) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)
    
    # Calculate option price
    if option_type.lower() == 'call':
        return S * stats.norm.cdf(d1) - K * math.exp(-r * T) * stats.norm.cdf(d2)
    else:  # put
        return K * math.exp(-r * T) * stats.norm.cdf(-d2) - S * stats.norm.cdf(-d1)


def bs_greeks(option_type, S, K, T, r, sigma):
    """
    Calculate option Greeks using Black-Scholes model.
    Returns NaN for Greeks if sigma is None or not numeric.
    
    Parameters:
    option_type: 'call' or 'put'
    S: spot price (current underlying price)
    K: strike price
    T: time to maturity in years (e.g., 5/365 for 5 days)
    r: risk-free rate (e.g., 0.05 for 5%)
    sigma: implied volatility (e.g., 0.20 for 20%)
    
    Returns:
    Dictionary containing delta, gamma, theta, vega
    """
    # Check if sigma is valid
    if sigma is None or math.isnan(sigma) or sigma <= 0:
        return {
            'delta': float('nan'),
            'gamma': float('nan'),
            'theta': float('nan'),
            'vega': float('nan')
        }
    
    # Ensure minimum time to maturity to avoid numerical issues
    T = max(T, 1/365)
    
    # Calculate d1 and d2
    d1 = (math.log(S/K) + (r + 0.5 * sigma**2) * T) / (sigma * math.sqrt(T))
    d2 = d1 - sigma * math.sqrt(T)
    
    # Standard normal CDF and PDF
    N_d1 = stats.norm.cdf(d1)
    N_d2 = stats.norm.cdf(d2)
    n_d1 = stats.norm.pdf(d1)
    
    # Greeks calculations
    if option_type.lower() == 'call':
        delta = N_d1
        theta = -(S * sigma * n_d1) / (2 * math.sqrt(T)) - r * K * math.exp(-r * T) * N_d2
    else:  # put
        delta = N_d1 - 1
        theta = -(S * sigma * n_d1) / (2 * math.sqrt(T)) + r * K * math.exp(-r * T) * (1 - N_d2)
    
    # Same for both call and put
    gamma = n_d1 / (S * sigma * math.sqrt(T))
    vega = S * math.sqrt(T) * n_d1 * 0.01  # scaled by 0.01 to get the impact of 1% change in vol
    
    return {
        'delta': delta,
        'gamma': gamma,
        'theta': theta,
        'vega': vega
    }


def estimate_vol_from_moneyness(moneyness, base_vol=0.20):
    """
    Estimate implied volatility based on option moneyness when market data isn't available.
    Uses the volatility smile approximation.
    
    Parameters:
    moneyness: Absolute value of (K/S - 1)
    base_vol: Base ATM volatility (default 20%)
    
    Returns:
    Estimated implied volatility
    """
    # Simple volatility smile approximation
    # ATM options have lowest vol, vol increases as you move away from ATM
    vol = base_vol + 0.5 * moneyness**2
    return min(vol, 1.5)  # Cap at 150% to avoid extreme values