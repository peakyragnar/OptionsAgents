#!/usr/bin/env python
"""Emergency gamma calculator - reads from existing queue"""
import asyncio
import time
from datetime import datetime
from src.persistence import append_gamma
from src.dealer.engine import _process_trade, _book
from src.stream.quote_cache import quote_cache

print(f"🚨 EMERGENCY GAMMA PROCESSOR - {datetime.now().strftime('%H:%M:%S')}")

# First, let's manually populate some quotes from recent data
# These are approximate based on SPX ~5875
test_quotes = {
    "I:SPX": {"bid": 5874, "ask": 5876},
    "O:SPXW250530C05875000": {"bid": 11.8, "ask": 12.2},
    "O:SPXW250530C05880000": {"bid": 9.5, "ask": 10.0},
    "O:SPXW250530C05885000": {"bid": 7.5, "ask": 8.0},
    "O:SPXW250530C05890000": {"bid": 5.5, "ask": 6.0},
    "O:SPXW250530C05895000": {"bid": 4.0, "ask": 4.5},
    "O:SPXW250530C05900000": {"bid": 3.0, "ask": 3.5},
    "O:SPXW250530C05905000": {"bid": 2.3, "ask": 2.7},
    "O:SPXW250530C05910000": {"bid": 1.7, "ask": 2.1},
    "O:SPXW250530P05875000": {"bid": 11.5, "ask": 12.0},
    "O:SPXW250530P05870000": {"bid": 9.0, "ask": 9.5},
    "O:SPXW250530P05860000": {"bid": 5.8, "ask": 6.3},
    "O:SPXW250530P05850000": {"bid": 3.8, "ask": 4.2},
}

# Update quote cache
quote_cache.update(test_quotes)
print(f"📊 Populated {len(test_quotes)} test quotes")

# Sample trades from the logs
sample_trades = [
    {"sym": "O:SPXW250530C05875000", "p": 12.0, "s": 1, "side": "SELL", "t": time.time() * 1e9},
    {"sym": "O:SPXW250530C05880000", "p": 10.0, "s": 2, "side": "BUY", "t": time.time() * 1e9},
    {"sym": "O:SPXW250530C05900000", "p": 3.4, "s": 1, "side": "SELL", "t": time.time() * 1e9},
    {"sym": "O:SPXW250530P05875000", "p": 11.6, "s": 1, "side": "BUY", "t": time.time() * 1e9},
    {"sym": "O:SPXW250530P05850000", "p": 4.1, "s": 1, "side": "BUY", "t": time.time() * 1e9},
]

async def process_sample_trades():
    print("\n🔄 Processing sample trades...")
    
    for i, trade in enumerate(sample_trades):
        try:
            await _process_trade(trade, eps=0.05)
            gamma = _book.total_gamma()
            print(f"Trade {i+1}: {trade['sym']} {trade['side']} {trade['s']}@{trade['p']} -> Total gamma: {gamma:.2f}")
        except Exception as e:
            print(f"Error processing trade {i+1}: {e}")
    
    # Save final snapshot
    final_gamma = _book.total_gamma()
    append_gamma(time.time(), final_gamma)
    print(f"\n✅ Final gamma: {final_gamma:.2f}")
    print("💾 Saved to database!")

asyncio.run(process_sample_trades())