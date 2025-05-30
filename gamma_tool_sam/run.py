#!/usr/bin/env python3
"""
Run Gamma Tool Sam - Real-time 0DTE directional gamma analysis
Integrates with existing OptionsAgents trade feed
"""

import asyncio
import sys
import os
from datetime import datetime
from pathlib import Path

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

from gamma_tool_sam.gamma_engine import GammaEngine
from gamma_tool_sam.utils.spx_price import get_spx_price
from src.stream.quote_cache import quotes
from src.stream.trade_feed import TRADE_Q

# Configuration
UPDATE_INTERVAL = 2  # Dashboard update frequency in seconds
SPX_QUOTE_KEY = 'I:SPX'  # SPX index quote key

class GammaToolSam:
    """Main runner for Gamma Tool Sam"""
    
    def __init__(self):
        self.engine = None
        self.running = False
        
    async def initialize(self):
        """Initialize the system"""
        print("🚀 Initializing Gamma Tool Sam...")
        
        # Get initial SPX price from Polygon
        print("📡 Fetching SPX price from Polygon...")
        spx_price = get_spx_price()
        print(f"✅ SPX Price: ${spx_price:,.2f}")
            
        # Initialize engine
        self.engine = GammaEngine(spx_price=spx_price)
        
        print("✅ Gamma Tool Sam initialized")
        
    async def process_trades(self):
        """Process trades from the queue"""
        print("📊 Starting trade processor...")
        
        while self.running:
            try:
                # Get trade from queue with timeout
                trade_data = await asyncio.wait_for(TRADE_Q.get(), timeout=1.0)
                
                # SPX price updates automatically in the engine
                
                # Process the trade
                processed = self.engine.trade_processor.process_trade(trade_data)
                
                if processed:
                    # Trade was processed successfully
                    stats = self.engine.trade_processor.get_stats()
                    if stats['trades_processed'] % 100 == 0:
                        print(f"📈 Processed {stats['trades_processed']} trades")
                        
            except asyncio.TimeoutError:
                # No trades in queue, continue
                pass
            except Exception as e:
                print(f"❌ Error processing trade: {e}")
                
    async def update_dashboard(self):
        """Update dashboard periodically"""
        print("🖥️  Starting dashboard updater...")
        
        while self.running:
            try:
                # Clear screen (optional - comment out if you prefer scrolling)
                # os.system('clear' if os.name == 'posix' else 'cls')
                
                # Print dashboard
                self.engine.print_human_dashboard()
                
                # Wait before next update
                await asyncio.sleep(UPDATE_INTERVAL)
                
            except Exception as e:
                print(f"❌ Dashboard error: {e}")
                await asyncio.sleep(UPDATE_INTERVAL)
                
    async def run(self):
        """Main run loop"""
        self.running = True
        
        try:
            # Initialize
            await self.initialize()
            
            # Create tasks
            tasks = [
                asyncio.create_task(self.process_trades()),
                asyncio.create_task(self.update_dashboard())
            ]
            
            print("\n" + "="*60)
            print("🎯 Gamma Tool Sam is running!")
            print("Waiting for trades...")
            print("="*60 + "\n")
            
            # Run until cancelled
            await asyncio.gather(*tasks)
            
        except KeyboardInterrupt:
            print("\n⚠️  Shutting down...")
        finally:
            self.running = False
            print("✅ Gamma Tool Sam stopped")

def main():
    """Main entry point"""
    print("""
    ╔═══════════════════════════════════════╗
    ║        GAMMA TOOL SAM v1.0            ║
    ║   Real-Time 0DTE Gamma Analysis       ║
    ║      Created by Sam's Method          ║
    ╚═══════════════════════════════════════╝
    """)
    
    # Check if running within OptionsAgents system
    if not TRADE_Q:
        print("❌ Error: Must run within OptionsAgents live system")
        print("Use: python -m src.cli live")
        return
        
    # Run the tool
    tool = GammaToolSam()
    asyncio.run(tool.run())

if __name__ == "__main__":
    main()