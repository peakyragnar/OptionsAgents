"""
Integration module for Gamma Tool Sam with main Options Agents system
This runs within the same process as the main CLI to access TRADE_Q
"""

import asyncio
import logging
from typing import Optional
from datetime import datetime
import threading

from .gamma_engine import GammaEngine
from .dashboard.web_dashboard import run_dashboard

logger = logging.getLogger(__name__)


async def run_gamma_tool_sam(engine: GammaEngine, trade_queue: asyncio.Queue):
    """
    Main integration function that processes trades from the main system's queue
    
    Args:
        engine: GammaEngine instance
        trade_queue: The TRADE_Q from src.stream.trade_feed
    """
    logger.info("🎯 Starting Gamma Tool Sam integration")
    
    # Start web dashboard in a thread
    dashboard_thread = threading.Thread(
        target=run_dashboard,
        args=(engine,),
        daemon=True
    )
    dashboard_thread.start()
    logger.info("✅ Web dashboard started on http://localhost:8080")
    
    # Process trades from the queue
    trades_processed = 0
    errors = 0
    
    while True:
        try:
            # Get trade from queue with timeout
            trade = await asyncio.wait_for(trade_queue.get(), timeout=1.0)
            
            # Process the trade through Gamma Tool Sam
            if trade:
                result = engine.process_trade(trade)
                if result:
                    trades_processed += 1
                    if trades_processed % 100 == 0:
                        logger.info(f"Gamma Tool Sam: Processed {trades_processed} trades")
                        
        except asyncio.TimeoutError:
            # Normal - no trades available
            continue
            
        except Exception as e:
            errors += 1
            logger.error(f"Error processing trade in Gamma Tool Sam: {e}")
            if errors > 100:
                logger.error("Too many errors in Gamma Tool Sam, restarting...")
                errors = 0
                await asyncio.sleep(5)
                
        await asyncio.sleep(0.001)  # Small delay to prevent CPU spin


async def test_integration():
    """Test function to verify integration is working"""
    logger.info("Testing Gamma Tool Sam integration...")
    
    # Create a test queue
    test_queue = asyncio.Queue()
    
    # Create engine
    engine = GammaEngine(spx_price=5920.0)
    
    # Add some test trades
    test_trades = [
        {
            'sym': 'O:SPXW240530C05900000',
            'price': 10.5,
            'size': 100,
            'exchange': 'CBOE',
            'timestamp': datetime.now().isoformat()
        },
        {
            'sym': 'O:SPXW240530P05800000',
            'price': 8.2,
            'size': 50,
            'exchange': 'CBOE', 
            'timestamp': datetime.now().isoformat()
        }
    ]
    
    for trade in test_trades:
        await test_queue.put(trade)
    
    # Run for a few seconds
    task = asyncio.create_task(run_gamma_tool_sam(engine, test_queue))
    await asyncio.sleep(5)
    task.cancel()
    
    logger.info("Integration test complete")


if __name__ == "__main__":
    # Run test
    asyncio.run(test_integration())