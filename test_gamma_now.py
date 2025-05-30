#!/usr/bin/env python
"""Quick test to verify gamma calculation works"""
import asyncio
from datetime import datetime
import time

# Test imports
try:
    from src.stream.quote_cache import quote_cache
    from src.dealer.engine import _process_trade, _book
    from src.utils.greeks import gamma as bs_gamma
    from src.utils.occ import parse as parse_occ
    print("✅ All imports successful")
except Exception as e:
    print(f"❌ Import error: {e}")
    exit(1)

# Simulate quote cache
quote_cache["O:SPXW250530C05900000"] = {"bid": 3.0, "ask": 3.2, "ts": time.time()}
quote_cache["I:SPX"] = {"bid": 5875, "ask": 5876, "ts": time.time()}

# Create test trade
test_trade = {
    "sym": "O:SPXW250530C05900000",
    "p": 3.20,  # At ask price (BUY)
    "s": 10,
    "t": int(time.time() * 1e9),  # Nanoseconds
    "price": 3.20,
    "size": 10,
    "timestamp": time.time()
}

async def test():
    print("\n📊 Testing dealer engine...")
    print(f"SPX: {quote_cache['I:SPX']['bid']}/{quote_cache['I:SPX']['ask']}")
    print(f"Option quote: {quote_cache[test_trade['sym']]['bid']}/{quote_cache[test_trade['sym']]['ask']}")
    print(f"Trade: {test_trade['sym']} {test_trade['s']}@{test_trade['p']}")
    
    # Process trade
    initial_gamma = _book.total_gamma()
    print(f"\nInitial gamma: {initial_gamma}")
    
    await _process_trade(test_trade, eps=0.05)
    
    final_gamma = _book.total_gamma()
    print(f"Final gamma: {final_gamma}")
    print(f"Gamma change: {final_gamma - initial_gamma}")
    
    if final_gamma != initial_gamma:
        print("\n✅ GAMMA CALCULATION WORKS!")
    else:
        print("\n❌ Gamma didn't change")

asyncio.run(test())