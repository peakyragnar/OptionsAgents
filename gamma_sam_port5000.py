#!/usr/bin/env python3
"""
Gamma Tool Sam - Port 5000 version
"""

import os
import time
import threading
from datetime import datetime

# Set the port
os.environ['FLASK_RUN_PORT'] = '5000'

from gamma_tool_sam.gamma_engine import GammaEngine
from gamma_tool_sam.dashboard.web_dashboard import run_dashboard
from gamma_tool_sam.utils.spx_price import get_spx_price

def update_spx_price_thread(engine, interval=15):
    """Update SPX price in a thread"""
    while True:
        try:
            price = get_spx_price()
            engine.update_spx_price(price)
            print(f"📊 Updated SPX: ${price:,.2f} at {datetime.now().strftime('%H:%M:%S')}")
        except Exception as e:
            print(f"❌ SPX update error: {e}")
        time.sleep(interval)

def main():
    print("""
    ╔════════════════════════════════════════════╗
    ║    GAMMA TOOL SAM - PORT 5000              ║
    ║         Web Dashboard Only                 ║
    ╚════════════════════════════════════════════╝
    """)
    
    # Get initial SPX price
    print("🔍 Fetching SPX price...")
    spx_price = get_spx_price()
    print(f"✅ Initial SPX: ${spx_price:,.2f}")
    
    # Create engine
    engine = GammaEngine(spx_price=spx_price)
    
    # Start SPX price updater
    price_thread = threading.Thread(
        target=update_spx_price_thread,
        args=(engine, 15),
        daemon=True
    )
    price_thread.start()
    
    # Start web dashboard on port 5000
    print("\n🌐 Starting web dashboard on port 5000...")
    print("✅ Dashboard will be available at http://localhost:5000")
    print("\nPress Ctrl+C to exit\n")
    
    # Run dashboard (blocking) on port 5000
    try:
        run_dashboard(engine, host='127.0.0.1', port=5000)
    except KeyboardInterrupt:
        print("\n⏹️  Shutting down...")

if __name__ == "__main__":
    main()