"""Shared in-process NBBO cache (used by nbbo_feed & unit-tests)."""

import logging
from typing import Dict, TypedDict
from src.utils.logging_config import setup_application_logging, setup_component_logger

# Initialize logging
setup_application_logging()
logger = setup_component_logger(__name__)

class Quote(TypedDict, total=False):
    bid:   float
    ask:   float
    ts:    int          # epoch-ms

quotes: Dict[str, Quote] = {}

# ----------------------------------------------------------------------
# backward-compat variable expected by trade_feed & dealer.engine tests
quote_cache = quotes    # <-- NEW ALIAS
import asyncio
async def run(poll_ms: int = 5000):
    """dummy poller so unit tests don't blow up."""
    while True:
        await asyncio.sleep(poll_ms / 1000)

def side_from_price(sym: str, px: float):
    quote = quotes.get(sym)
    if not quote:
        return None
    bid = quote.get("bid")
    ask = quote.get("ask")
    if bid is None or ask is None:
        return None
    if px >= ask - 1e-4:
        return "buy"
    if px <= bid + 1e-4:
        return "sell"
    return None