"""
Shared queue for communication between unified feed and dealer engine.
This ensures both components use the same asyncio.Queue instance.
"""
import asyncio
from typing import Optional

# Global queue instance
_TRADE_QUEUE: Optional[asyncio.Queue] = None

def get_trade_queue() -> asyncio.Queue:
    """Get the shared trade queue, creating it if necessary."""
    global _TRADE_QUEUE
    if _TRADE_QUEUE is None:
        _TRADE_QUEUE = asyncio.Queue()
        print(f"[shared_queue] Created trade queue: {id(_TRADE_QUEUE)} in event loop: {id(asyncio.get_event_loop())}")
    return _TRADE_QUEUE

def reset_trade_queue():
    """Reset the trade queue (mainly for testing)."""
    global _TRADE_QUEUE
    _TRADE_QUEUE = None