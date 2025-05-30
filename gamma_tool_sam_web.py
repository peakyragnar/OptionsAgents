#!/usr/bin/env python3
"""
Gamma Tool Sam - Web Dashboard Mode
Standalone runner with Polygon SPX price feed
"""

import asyncio
import threading
from datetime import datetime

from gamma_tool_sam.gamma_engine import GammaEngine
from gamma_tool_sam.dashboard.web_dashboard import run_dashboard
from gamma_tool_sam.utils.spx_price import get_spx_price, update_spx_price_loop

# Import existing components
from src.stream.trade_feed import TRADE_Q
from src.stream.quote_cache import quotes


async def process_trades(engine):
    """Process trades from the queue"""
    print("📡 Waiting for trades from main system...")
    processed = 0
    no_trade_counter = 0
    
    while True:
        try:
            # Check if TRADE_Q exists and has trades
            if TRADE_Q is None:
                if no_trade_counter == 0:
                    print("⚠️  Trade queue not available. Start main system with: python -m src.cli live")
                no_trade_counter += 1
                await asyncio.sleep(5)
                continue
                
            # Get trade with timeout
            trade = await asyncio.wait_for(TRADE_Q.get(), timeout=0.5)
            
            # Only process SPX options
            if trade and 'O:SPX' in trade.get('symbol', ''):
                engine.trade_processor.process_trade(trade)
                processed += 1
                
                if processed % 50 == 0:
                    print(f"📈 Processed {processed} trades")
                    
        except asyncio.TimeoutError:
            continue
        except AttributeError:
            # TRADE_Q doesn't have get method
            if no_trade_counter == 0:
                print("⚠️  Trade queue not initialized. Waiting...")
            no_trade_counter += 1
            await asyncio.sleep(5)
        except Exception as e:
            print(f"❌ Error: {e}")


async def main():
    """Main async function"""
    print("""
    ╔════════════════════════════════════════════╗
    ║      GAMMA TOOL SAM - WEB DASHBOARD        ║
    ║    Real-Time 0DTE Directional Analysis     ║
    ╚════════════════════════════════════════════╝
    """)
    
    # Get initial SPX price
    print("🔍 Fetching SPX price from Polygon...")
    spx_price = get_spx_price()
    print(f"✅ SPX: ${spx_price:,.2f}")
    
    # Create engine
    engine = GammaEngine(spx_price=spx_price)
    
    # Start web dashboard in thread
    print("🌐 Starting web dashboard...")
    dashboard_thread = threading.Thread(
        target=run_dashboard,
        args=(engine,),
        daemon=True
    )
    dashboard_thread.start()
    
    print("✅ Dashboard running at http://localhost:8080")
    print("-" * 50)
    
    # Start SPX price updater and trade processor
    tasks = [
        update_spx_price_loop(engine, interval=15),  # SPX updater
        process_trades(engine),  # Trade processor
    ]
    
    print("ℹ️  Note: This should be run alongside 'python -m src.cli live'")
    print("   The main system provides the trade feed and quotes.")
    
    print("📡 Connecting to Polygon WebSocket...")
    print("⏳ Waiting for market data...\n")
    
    try:
        await asyncio.gather(*tasks)
    except KeyboardInterrupt:
        print("\n⏹️  Shutting down...")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n✅ Gamma Tool Sam stopped")