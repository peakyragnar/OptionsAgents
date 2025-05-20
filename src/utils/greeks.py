"""
Option Greeks calculation utilities using Black-Scholes model.
Includes functions for calculating implied volatility and option Greeks.
"""
import math
from scipy.stats import norm
from scipy.optimize import brentq

def bs_price(s, k, iv, tau, cp):
    """
    Calculate option price using Black-Scholes formula.
    
    Parameters:
    s: spot price (current underlying price)
    k: strike price
    iv: implied volatility
    tau: time to maturity in years (e.g., 5/365 for 5 days)
    cp: option type ('C' for call, 'P' for put)
    
    Returns:
    Option price
    """
    d1 = (math.log(s / k) + 0.5 * iv**2 * tau) / (iv * math.sqrt(tau))
    d2 = d1 - iv * math.sqrt(tau)
    if cp == "C":
        return s * norm.cdf(d1) - k * norm.cdf(d2)
    else:  # Put via put-call parity
        return k * norm.cdf(-d2) - s * norm.cdf(-d1)

def implied_vol(price, s, k, tau, cp):
    """
    Calculate implied volatility using Brent's method.
    Return sigma or None if root-find fails.
    
    Parameters:
    price: market price of the option
    s: spot price (current underlying price)
    k: strike price
    tau: time to maturity in years (e.g., 5/365 for 5 days)
    cp: option type ('C' for call, 'P' for put)
    
    Returns:
    Implied volatility as a float or None if calculation fails
    """
    # Ensure minimum time to maturity to avoid numerical issues
    tau = max(tau, 1/365)
    
    try:
        f = lambda sigma: bs_price(s, k, sigma, tau, cp) - price
        return brentq(f, 1e-4, 3.0, maxiter=100, rtol=1e-6)
    except Exception:
        return None

def bs_greeks(s, k, iv, tau, cp):
    """
    Calculate option Greeks using Black-Scholes model.
    
    Parameters:
    s: spot price (current underlying price)
    k: strike price
    iv: implied volatility
    tau: time to maturity in years (e.g., 5/365 for 5 days)
    cp: option type ('C' for call, 'P' for put)
    
    Returns:
    gamma, vega, theta as a tuple
    """
    # Ensure minimum time to maturity and valid IV
    tau = max(tau, 1/365)
    if iv is None or math.isnan(iv) or iv <= 0:
        return float('nan'), float('nan'), float('nan')
    
    d1 = (math.log(s / k) + 0.5 * iv**2 * tau) / (iv * math.sqrt(tau))
    d2 = d1 - iv * math.sqrt(tau)
    phi = norm.pdf(d1)
    
    # Greek calculations
    gamma = phi / (s * iv * math.sqrt(tau))
    vega = s * phi * math.sqrt(tau) / 100  # per 1 vol-pt
    theta = (- (s * phi * iv) / (2 * math.sqrt(tau))) / 365  # daily theta
    
    return gamma, vega, theta

# Backward compatibility for older code
def bs_greeks_dict(option_type, S, K, T, r, sigma):
    """
    Legacy wrapper for backward compatibility.
    Calculate option Greeks using Black-Scholes model.
    Returns dictionary of Greeks.
    
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
    
    # Convert option_type to cp format
    cp = "C" if option_type.lower() == 'call' else "P"
    
    # Calculate Greeks using new function
    gamma, vega, theta = bs_greeks(S, K, sigma, T, cp)
    
    # Calculate delta separately since it's not in the new function
    d1 = (math.log(S/K) + (r + 0.5 * sigma**2) * T) / (sigma * math.sqrt(T))
    delta = norm.cdf(d1) if cp == "C" else norm.cdf(d1) - 1
    
    return {
        'delta': delta,
        'gamma': gamma,
        'theta': theta,
        'vega': vega
    }

# For backward compatibility
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

# Functions required by the engine test
def gamma(s, k, iv, tau, cp=None):
    """
    Extract gamma from bs_greeks for backward compatibility.
    
    Parameters:
    s: spot price
    k: strike price
    iv: implied volatility
    tau: time to expiry in years
    cp: option type (ignored, included for compatibility)
    
    Returns:
    gamma value only
    """
    g, _, _ = bs_greeks(s, k, iv, tau, "C" if cp is None else cp)
    return g

# Call-specific implied vol function
def implied_vol_call(price, s, k, tau, r=0, q=0):
    """
    Calculate implied volatility for call options.
    Wrapper around implied_vol for backward compatibility.
    
    Parameters:
    price: option price
    s: spot price
    k: strike price
    tau: time to expiry in years
    r: risk-free rate (ignored, included for compatibility)
    q: dividend yield (ignored, included for compatibility)
    
    Returns:
    implied volatility
    """
    return implied_vol(price, s, k, tau, "C")

# Put-specific implied vol function for symmetry
def implied_vol_put(price, s, k, tau, r=0, q=0):
    """
    Calculate implied volatility for put options.
    Wrapper around implied_vol for backward compatibility.
    
    Parameters:
    price: option price
    s: spot price
    k: strike price
    tau: time to expiry in years
    r: risk-free rate (ignored, included for compatibility)
    q: dividend yield (ignored, included for compatibility)
    
    Returns:
    implied volatility
    """
    return implied_vol(price, s, k, tau, "P")