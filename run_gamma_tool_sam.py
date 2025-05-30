#!/usr/bin/env python3
"""
Standalone runner for Gamma Tool Sam
Integrates with the existing OptionsAgents live trading system
"""

import asyncio
import os
from datetime import datetime
from typing import Optional
import threading
import time

# Import the existing OptionsAgents components
from src.stream.quote_cache import quotes, run as quotes_run
from src.stream.trade_feed import TRADE_Q, run as trades_run
from src.dealer.engine import _book

# Import Gamma Tool Sam
from gamma_tool_sam.gamma_engine import GammaEngine
from gamma_tool_sam.utils.spx_price import get_spx_price, update_spx_price_loop

# Configuration
DASHBOARD_UPDATE_INTERVAL = 3  # seconds
SPX_PRICE_UPDATE_INTERVAL = 5  # seconds

class GammaToolSamRunner:
    """Runs Gamma Tool Sam alongside existing systems"""
    
    def __init__(self):
        self.engine = None
        self.running = False
        self.spx_price = None
        
    def get_spx_price(self) -> float:
        """Get current SPX price from Polygon"""
        return get_spx_price()
        
    async def initialize(self):
        """Initialize Gamma Tool Sam"""
        print("🚀 Initializing Gamma Tool Sam...")
        
        # Get initial SPX price
        self.spx_price = self.get_spx_price()
        print(f"📊 Initial SPX Price: ${self.spx_price:,.2f}")
        
        # Create engine
        self.engine = GammaEngine(spx_price=self.spx_price)
        
        print("✅ Gamma Tool Sam initialized")
        
    async def process_trades(self):
        """Process trades from the existing trade queue"""
        processed_count = 0
        
        while self.running:
            try:
                # Check for trades with timeout
                trade = await asyncio.wait_for(TRADE_Q.get(), timeout=0.1)
                
                # Process through Gamma Tool Sam
                if trade and trade.get('symbol', '').startswith('O:SPX'):
                    self.engine.trade_processor.process_trade(trade)
                    processed_count += 1
                    
                    # SPX price now updates automatically via update_spx_price_loop
                    if processed_count % 100 == 0:
                        logger_msg = f"Processed {processed_count} trades"
                        if hasattr(self.engine.gamma_calculator, 'spx_price'):
                            logger_msg += f" | SPX: ${self.engine.gamma_calculator.spx_price:,.2f}"
                        print(f"📊 {logger_msg}")
                            
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                print(f"❌ Trade processing error: {e}")
                
    def print_dashboard(self):
        """Print the dashboard in a separate thread"""
        while self.running:
            try:
                # Clear screen for clean display
                os.system('clear' if os.name == 'posix' else 'cls')
                
                # Print header
                print(f"\n🕐 {datetime.now().strftime('%H:%M:%S')} | Gamma Tool Sam")
                
                # Print gamma analysis
                self.engine.print_human_dashboard()
                
                # Print integration status
                print(f"\n📡 Integration Status:")
                print(f"   Quote Cache: {'✅ Active' if quotes else '❌ Inactive'}")
                print(f"   Trade Queue: {'✅ Receiving' if not TRADE_Q.empty() else '⏳ Waiting'}")
                print(f"   SPX Price: ${self.spx_price:,.2f}")
                
                time.sleep(DASHBOARD_UPDATE_INTERVAL)
                
            except Exception as e:
                print(f"❌ Dashboard error: {e}")
                time.sleep(DASHBOARD_UPDATE_INTERVAL)
                
    async def run(self):
        """Main run loop"""
        self.running = True
        
        try:
            # Initialize
            await self.initialize()
            
            # Start dashboard in separate thread
            dashboard_thread = threading.Thread(target=self.print_dashboard)
            dashboard_thread.daemon = True
            dashboard_thread.start()
            
            # Start SPX price updater
            spx_task = asyncio.create_task(update_spx_price_loop(self.engine, interval=10))
            
            # Process trades
            await asyncio.gather(
                self.process_trades(),
                spx_task
            )
            
        except KeyboardInterrupt:
            print("\n⚠️  Shutting down Gamma Tool Sam...")
        finally:
            self.running = False
            
def main():
    """Main entry point"""
    print("""
    ════════════════════════════════════════
         GAMMA TOOL SAM - LIVE MODE
    ════════════════════════════════════════
    
    Real-time 0DTE directional gamma analysis
    Tracking institutional option selling
    
    Starting up...
    """)
    
    # Create tasks for all components
    async def run_all():
        # Run existing OptionsAgents components
        quotes_task = asyncio.create_task(quotes_run())
        trades_task = asyncio.create_task(trades_run())
        
        # Give them time to initialize
        await asyncio.sleep(2)
        
        # Run Gamma Tool Sam
        runner = GammaToolSamRunner()
        await runner.run()
        
    # Run everything
    try:
        asyncio.run(run_all())
    except KeyboardInterrupt:
        print("\n✅ Gamma Tool Sam stopped")
        
if __name__ == "__main__":
    main()