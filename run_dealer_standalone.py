#!/usr/bin/env python
"""Standalone dealer engine - monitors live feed output for trades"""
import re
import time
import asyncio
from datetime import datetime
from collections import deque

from src.persistence import append_gamma  
from src.dealer.engine import _process_trade, _book
from src.stream.quote_cache import quote_cache

print(f"🚀 STANDALONE DEALER ENGINE - {datetime.now().strftime('%H:%M:%S')}")
print("📊 Monitoring live.out for trades...")

# Populate quote cache with recent market data
base_quotes = {
    "I:SPX": {"bid": 5874, "ask": 5876}
}

# Generate quotes for strikes around current SPX
spx = 5875
for strike in range(5700, 6000, 5):
    # Rough approximation of option prices
    dist = abs(strike - spx)
    if dist < 50:
        base_price = 15 - (dist * 0.2)
    else:
        base_price = max(0.05, 5 - (dist - 50) * 0.05)
    
    # Calls
    call_sym = f"O:SPXW250530C{strike:05d}000"
    base_quotes[call_sym] = {"bid": base_price * 0.95, "ask": base_price * 1.05}
    
    # Puts  
    put_sym = f"O:SPXW250530P{strike:05d}000"
    base_quotes[put_sym] = {"bid": base_price * 0.95, "ask": base_price * 1.05}

quote_cache.update(base_quotes)
print(f"📊 Populated {len(base_quotes)} quotes")

# Parse trades from log output
trade_pattern = re.compile(r'Pushed trade #(\d+).*?: (O:SPXW\d+[CP]\d+) (BUY|SELL|\?) (\d+)@([\d.]+)')

async def process_log_trades():
    """Read trades from log file and process them"""
    trades_processed = 0
    last_snapshot = time.time()
    
    # Open log file and seek to near end
    with open('/Users/michael/logs/live.out', 'r') as f:
        # Go to end of file
        f.seek(0, 2)
        # Back up 10KB to catch recent trades
        f.seek(max(0, f.tell() - 10000))
        f.readline()  # Skip partial line
        
        print("📖 Reading recent trades from log...")
        
        while True:
            line = f.readline()
            if not line:
                # Check if it's time for a snapshot
                now = time.time()
                if now - last_snapshot >= 1.0 and trades_processed > 0:
                    gamma = _book.total_gamma()
                    append_gamma(now, gamma)
                    print(f"💾 Snapshot: {trades_processed} trades, gamma={gamma:.2f}")
                    last_snapshot = now
                
                await asyncio.sleep(0.1)
                continue
            
            # Parse trade from log
            match = trade_pattern.search(line)
            if match:
                trade_num, symbol, side, size, price = match.groups()
                
                # Create trade message
                trade = {
                    "sym": symbol,
                    "p": float(price),
                    "s": int(size),
                    "t": int(time.time() * 1e9),
                    "side": side if side != "?" else None
                }
                
                try:
                    await _process_trade(trade, eps=0.05)
                    trades_processed += 1
                    
                    if trades_processed % 10 == 0:
                        gamma = _book.total_gamma()
                        print(f"📈 Processed {trades_processed} trades, gamma={gamma:.2f}")
                        
                except Exception as e:
                    print(f"Error processing trade: {e}")

try:
    asyncio.run(process_log_trades())
except KeyboardInterrupt:
    print("\n👋 Shutting down...")
    final_gamma = _book.total_gamma()
    append_gamma(time.time(), final_gamma)
    print(f"💾 Final snapshot: gamma={final_gamma:.2f}")