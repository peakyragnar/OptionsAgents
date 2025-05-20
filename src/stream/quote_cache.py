# ---------- src/stream/quote_cache.py ----------
"""
Thread-safe in-memory cache for NBBO quotes.
"""

import threading
from typing import Dict, Any

class QuoteCache:
    def __init__(self) -> None:
        self._lock   = threading.RLock()
        self._quotes: Dict[str, Dict[str, Any]] = {}

    # --------------------------------------------------------------------- #
    # called by nbbo_feed.py
    def update(self, *, symbol: str, bid: float, bid_size: int,
               ask: float, ask_size: int, ts: int) -> None:
        with self._lock:
            self._quotes[symbol] = {
                "bid":       bid,
                "bid_size":  bid_size,
                "ask":       ask,
                "ask_size":  ask_size,
                "ts":        ts,        # unix-ms
            }

    # --------------------------------------------------------------------- #
    # used by trade_feed.py / cli
    def get(self, symbol: str):
        with self._lock:
            return self._quotes.get(symbol)

    # optional helper
    def snapshot(self):
        with self._lock:
            return dict(self._quotes)

# ------------------------------------------------------------------------- #
# **THIS** is what the other modules import
quote_cache = QuoteCache()