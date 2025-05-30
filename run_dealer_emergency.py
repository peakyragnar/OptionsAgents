#!/usr/bin/env python
"""Emergency dealer engine runner - bypasses CLI issues"""
import asyncio
import sys
from datetime import datetime

# Add the project to path
sys.path.insert(0, '/Users/michael/OptionsAgents')

from src.dealer.engine import run as engine_run
from src.persistence import append_gamma
from src.stream.unified_feed import TRADE_Q
from src.stream.quote_cache import quote_cache

print(f"🚨 EMERGENCY DEALER ENGINE START - {datetime.now().strftime('%H:%M:%S')}")
print(f"📊 Initial queue size: {TRADE_Q.qsize()}")
print(f"💾 Quote cache size: {len(quote_cache)}")

async def monitor_loop():
    """Monitor queue and gamma every 10 seconds"""
    while True:
        await asyncio.sleep(10)
        print(f"📊 Queue size: {TRADE_Q.qsize()}, Quote cache: {len(quote_cache)}")

async def main():
    # Start monitoring task
    monitor_task = asyncio.create_task(monitor_loop())
    
    # Run dealer engine
    print("🚀 Starting dealer engine...")
    try:
        await engine_run(append_gamma, eps=0.05, snapshot_interval=1.0)
    except Exception as e:
        print(f"❌ Engine crashed: {e}")
        import traceback
        traceback.print_exc()
    
    monitor_task.cancel()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Shutting down...")