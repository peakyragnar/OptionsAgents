#!/usr/bin/env python3
"""
Complete runner for Gamma Tool Sam with web dashboard
Run this to start the full system with visual interface
"""

import asyncio
import threading
import sys
import os
from pathlib import Path
from datetime import datetime

# Add to Python path
sys.path.append(str(Path(__file__).parent))

# Import OptionsAgents components
from src.stream.quote_cache import quotes, run as quotes_run
from src.stream.trade_feed import TRADE_Q, run as trades_run

# Import Gamma Tool Sam
from gamma_tool_sam.gamma_engine import GammaEngine
from gamma_tool_sam.dashboard.web_dashboard import run_dashboard

# Configuration
WEB_PORT = 8080
SPX_QUOTE_KEY = 'I:SPX'

class GammaSamLive:
    """Complete Gamma Tool Sam system with web interface"""
    
    def __init__(self):
        self.engine = None
        self.running = False
        
    def get_spx_price(self):
        """Get current SPX price"""
        # Try quote cache
        spx_quote = quotes.get(SPX_QUOTE_KEY)
        if spx_quote and spx_quote[0] > 0:
            return (spx_quote[0] + spx_quote[1]) / 2
            
        # Try recent parquet
        try:
            import duckdb
            conn = duckdb.connect(':memory:')
            result = conn.execute("""
                SELECT under_px 
                FROM read_parquet('data/parquet/spx/date=*/**.parquet')
                WHERE date = CURRENT_DATE
                AND under_px IS NOT NULL
                ORDER BY filename DESC
                LIMIT 1
            """).fetchone()
            conn.close()
            
            if result and result[0]:
                return float(result[0])
        except:
            pass
            
        return 5900.0  # Fallback
        
    async def process_trades(self):
        """Process trades from the feed"""
        print("📊 Trade processor started")
        
        while self.running:
            try:
                # Get trade from queue
                trade = await asyncio.wait_for(TRADE_Q.get(), timeout=0.5)
                
                if trade and 'SPX' in trade.get('symbol', ''):
                    # Update SPX price periodically
                    if self.engine.trade_processor.trades_processed % 20 == 0:
                        spx = self.get_spx_price()
                        self.engine.gamma_calculator.update_spx_price(spx)
                    
                    # Process trade
                    self.engine.trade_processor.process_trade(trade)
                    
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                print(f"Trade error: {e}")
                
    def run_web_dashboard(self):
        """Run web dashboard in separate thread"""
        run_dashboard(self.engine, host='0.0.0.0', port=WEB_PORT)
        
    async def run(self):
        """Main run loop"""
        self.running = True
        
        print("""
╔═══════════════════════════════════════════╗
║         GAMMA TOOL SAM - LIVE MODE        ║
║                                           ║
║   Real-Time 0DTE Directional Gamma        ║
║   Created by Sam's Methodology            ║
╚═══════════════════════════════════════════╝
        """)
        
        # Initialize engine
        print("\n🚀 Initializing system...")
        spx_price = self.get_spx_price()
        print(f"📊 SPX Price: ${spx_price:,.2f}")
        
        self.engine = GammaEngine(spx_price=spx_price)
        
        # Start web dashboard in thread
        print(f"\n🌐 Starting web dashboard on port {WEB_PORT}...")
        dashboard_thread = threading.Thread(target=self.run_web_dashboard)
        dashboard_thread.daemon = True
        dashboard_thread.start()
        
        print(f"\n✅ Dashboard available at: http://localhost:{WEB_PORT}")
        print("\n⏳ Waiting for trades...\n")
        
        try:
            # Process trades
            await self.process_trades()
            
        except KeyboardInterrupt:
            print("\n⚠️  Shutting down...")
        finally:
            self.running = False

async def main():
    """Main entry point"""
    # Create all tasks
    tasks = []
    
    # Start quote cache
    print("📡 Starting quote cache...")
    tasks.append(asyncio.create_task(quotes_run()))
    
    # Start trade feed with SPX options
    print("📡 Starting trade feed...")
    # SPX options pattern for 0DTE
    tickers = ["O:SPX*"]  # This will capture all SPX options
    tasks.append(asyncio.create_task(trades_run(tickers)))
    
    # Give feeds time to initialize
    await asyncio.sleep(3)
    
    # Start Gamma Tool Sam
    runner = GammaSamLive()
    tasks.append(asyncio.create_task(runner.run()))
    
    # Run everything
    try:
        await asyncio.gather(*tasks)
    except KeyboardInterrupt:
        print("\n✅ System stopped")

if __name__ == "__main__":
    # Check for required directories
    os.makedirs('data/gamma_tool_sam/positions', exist_ok=True)
    os.makedirs('data/gamma_tool_sam/trades', exist_ok=True)
    os.makedirs('data/gamma_tool_sam/analysis', exist_ok=True)
    
    # Run the system
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")