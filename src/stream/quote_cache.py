"""Shared in-process NBBO cache (used by nbbo_feed & unit-tests)."""

from typing import Dict, TypedDict

class Quote(TypedDict, total=False):
    bid:   float
    ask:   float
    ts:    int          # epoch-ms

quotes: Dict[str, Quote] = {}

# ----------------------------------------------------------------------
# backward-compat variable expected by trade_feed & dealer.engine tests
quote_cache = quotes    # <-- NEW ALIAS