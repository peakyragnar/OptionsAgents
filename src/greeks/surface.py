# src/greeks/surface.py
"""
VolSurface
----------
Cache implied vols for intraday quotes.

Usage
-----
vs = VolSurface(eps=0.02, ttl=60.0)
sigma = vs.get_sigma(sym, mid_price, S, K, tau)   # returns cached or recalculated σ
"""

from __future__ import annotations
import time
from dataclasses import dataclass

from src.utils.greeks import implied_vol_call as iv_call

@dataclass
class _CacheRow:
    sigma: float
    mid_ref: float
    ts: float          # UNIX seconds

class VolSurface:
    def __init__(self, *, eps: float = 0.02, ttl: float = 60.0):
        """
        eps : fractional mid-price move that triggers a new IV solve (e.g. 0.02 → 2 %).
        ttl : seconds after which σ expires regardless of price drift.
        """
        self.eps  = eps
        self.ttl  = ttl
        self._map: dict[str, _CacheRow] = {}

    # ------------------------------------------------------------------
    def get_sigma(self, sym: str, mid: float, S: float,
                  K: float, tau: float, r: float = 0.0, q: float = 0.0) -> float:
        """
        Return implied vol for *sym* given the latest mid-price.
        Recalculate if (|mid – mid_ref| / mid_ref) > eps  or  age > ttl.
        """
        now = time.time()
        row = self._map.get(sym)
        
        # Check if we need to recalculate
        needs_recalc = False
        
        if row is None:
            needs_recalc = True
        elif row.mid_ref is None:  # Handle case when mid_ref is None
            needs_recalc = True
        elif abs(mid - row.mid_ref) / (row.mid_ref or 1.0) > self.eps:  # Avoid division by zero
            needs_recalc = True
        elif (now - row.ts) > self.ttl:
            needs_recalc = True
            
        if needs_recalc:
            try:
                # Protect against invalid inputs
                if not (S > 0 and K > 0 and tau > 0 and mid >= 0):
                    # If inputs are invalid, use a reasonable default or last known value
                    if row is not None:
                        return row.sigma
                    return 0.2  # Default 20% volatility
                    
                # Calculate implied volatility
                sigma = iv_call(mid, S, K, tau, r, q)
                
                # If calculation succeeded, update cache
                if sigma is not None and sigma > 0:
                    self._map[sym] = _CacheRow(sigma, mid, now)
                    return sigma
                else:
                    # If calculation failed, use moneyness-based estimate
                    moneyness = abs(K / S - 1.0)
                    # Simple volatility smile approximation
                    est_vol = 0.2 + 0.15 * moneyness  # Base vol + skew
                    self._map[sym] = _CacheRow(est_vol, mid, now)
                    return est_vol
            except Exception as e:
                # Log exception (in a real system)
                print(f"[surface] Error calculating IV for {sym}: {e}")
                # Return default or last known value
                if row is not None:
                    return row.sigma
                return 0.2  # Default 20% volatility
                
        # Return cached value
        return row.sigma

    # convenience
    def clear(self) -> None:
        self._map.clear()