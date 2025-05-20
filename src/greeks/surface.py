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

from src.utils.greeks import implied_vol as iv_call   # adjust if your fn name differs

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

        if (
            row is None or
            abs(mid - row.mid_ref) / row.mid_ref > self.eps or
            (now - row.ts) > self.ttl
        ):
            sigma = iv_call(mid, S, K, tau, r, q)
            self._map[sym] = _CacheRow(sigma, mid, now)
            return sigma
        return row.sigma

    # convenience
    def clear(self) -> None:
        self._map.clear()