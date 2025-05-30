#!/usr/bin/env python3
"""
Run Gamma Tool Sam with simulated trades for testing
Perfect for after-hours development and testing
"""

import asyncio
import threading
from datetime import datetime

# Import components
from gamma_tool_sam.gamma_engine import GammaEngine
from gamma_tool_sam.dashboard.web_dashboard import run_dashboard
from simulate_gamma_trades import TradeSimulator
from src.stream.trade_feed import TRADE_Q

WEB_PORT = 8080

class GammaSamTest:
    """Run Gamma Tool Sam with simulated data"""
    
    def __init__(self):
        self.engine = None
        self.simulator = None
        self.running = False
        
    async def process_trades(self):
        """Process simulated trades"""
        print("📊 Trade processor ready for simulated data")
        
        while self.running:
            try:
                trade = await asyncio.wait_for(TRADE_Q.get(), timeout=0.5)
                
                if trade:
                    # Update SPX price from simulator
                    if self.simulator and hasattr(self.simulator, 'spx_price'):
                        self.engine.gamma_calculator.update_spx_price(self.simulator.spx_price)
                    
                    # Process trade
                    self.engine.trade_processor.process_trade(trade)
                    
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                print(f"Processing error: {e}")
                
    def run_web_dashboard(self):
        """Run web dashboard"""
        run_dashboard(self.engine, host='0.0.0.0', port=WEB_PORT)
        
    async def run(self):
        """Main run loop"""
        self.running = True
        
        print("""
╔═══════════════════════════════════════════╗
║     GAMMA TOOL SAM - TEST MODE            ║
║                                           ║
║   Using Simulated SPX 0DTE Trades         ║
║   Perfect for After-Hours Testing         ║
╚═══════════════════════════════════════════╝
        """)
        
        # Initialize engine
        print("\n🚀 Initializing Gamma Tool Sam...")
        self.engine = GammaEngine(spx_price=5905.77)
        
        # Start web dashboard
        print(f"\n🌐 Starting web dashboard on port {WEB_PORT}...")
        dashboard_thread = threading.Thread(target=self.run_web_dashboard)
        dashboard_thread.daemon = True
        dashboard_thread.start()
        
        print(f"\n✅ Dashboard available at: http://localhost:{WEB_PORT}")
        
        # Initialize trade simulator
        print("\n🎲 Starting trade simulator...")
        self.simulator = TradeSimulator()
        
        # Create tasks
        tasks = [
            asyncio.create_task(self.simulator.run()),
            asyncio.create_task(self.process_trades())
        ]
        
        print("\n📈 Generating simulated trades...")
        print("   - Market open surge simulation")
        print("   - Random trades with realistic patterns")
        print("   - Periodic pin formation events")
        print("\n⏳ Watch the dashboard update in real-time!\n")
        
        try:
            await asyncio.gather(*tasks)
        except KeyboardInterrupt:
            print("\n⚠️ Shutting down...")
        finally:
            self.running = False
            if self.simulator:
                self.simulator.stop()

async def main():
    runner = GammaSamTest()
    await runner.run()

if __name__ == "__main__":
    import os
    
    # Create required directories
    os.makedirs('data/gamma_tool_sam/positions', exist_ok=True)
    os.makedirs('data/gamma_tool_sam/trades', exist_ok=True)
    os.makedirs('data/gamma_tool_sam/analysis', exist_ok=True)
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Test complete!")