#!/usr/bin/env python
"""Diagnose why dealer engine isn't consuming from queue"""
import asyncio
from src.stream.unified_feed import TRADE_Q
from src.stream.quote_cache import quote_cache

print(f"🔍 TRADE_Q type: {type(TRADE_Q)}")
print(f"🔍 TRADE_Q size: {TRADE_Q.qsize()}")
print(f"🔍 Quote cache size: {len(quote_cache)}")

# Try to get a trade
async def test():
    try:
        # Try to get a trade with timeout
        trade = await asyncio.wait_for(TRADE_Q.get(), timeout=1.0)
        print(f"✅ Got trade from queue: {trade}")
    except asyncio.TimeoutError:
        print("❌ Timeout waiting for trade")
    except Exception as e:
        print(f"❌ Error getting trade: {e}")

asyncio.run(test())