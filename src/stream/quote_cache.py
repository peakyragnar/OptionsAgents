"""Shared in-process NBBO cache (used by nbbo_feed & tests)."""
from typing import Dict, TypedDict

class Quote(TypedDict, total=False):
    bid: float
    ask: float
    ts:  int          # epoch-milliseconds

quotes: Dict[str, Quote] = {}