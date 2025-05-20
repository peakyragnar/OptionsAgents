"""
Ultra-simple test for Polygon's WebSocket that subscribes to a broader set of data
to confirm data flow.
"""

import os
import asyncio
import json
import aiohttp
import sys
from dotenv import load_dotenv
load_dotenv()

# Print with flush
def print_flush(msg):
    print(msg, flush=True)
    sys.stdout.flush()

async def test_polygon():
    """Test Polygon WebSocket with minimal subscription."""
    # Get API key from environment
    api_key = os.environ.get("POLYGON_KEY", "DUMMY_KEY")
    
    # Connect to Polygon WebSocket
    url = f"wss://socket.polygon.io/options?apiKey={api_key}"
    print_flush(f"Connecting to {url}")
    
    async with aiohttp.ClientSession() as session:
        async with session.ws_connect(url, heartbeat=30) as ws:
            print_flush("Connected to WebSocket")
            
            # Authenticate
            await ws.send_json({"action": "auth", "params": api_key})
            auth_resp = await ws.receive()
            if auth_resp.type == aiohttp.WSMsgType.TEXT:
                print_flush(f"Auth response: {auth_resp.data}")
            
            # Subscribe to a few different types of data
            # Based on Polygon's docs: https://polygon.io/docs/options/ws_options
            
            # 1. Try multiple option subscriptions to find active trading
            # Subscribe to both SPX and SPXW options with wildcards
            spx_params = [
                "OT.O:SPX*",    # All SPX options
                "OT.O:SPXW*",   # All SPXW options (weekly)
                "OT.*"          # All option trades (as a fallback)
            ]
            await ws.send_json({"action": "subscribe", "params": spx_params})
            print_flush(f"Subscribed to options trades with: {spx_params}")
            
            # Wait for response
            sub_resp = await ws.receive()
            print_flush(f"Subscription response: {sub_resp.data if sub_resp.type == aiohttp.WSMsgType.TEXT else sub_resp}")
            
            # Listen for 60 seconds to give more time for trades to come in
            print_flush("Listening for messages for 60 seconds...")
            end_time = asyncio.get_event_loop().time() + 60
            trade_count = 0
            
            while asyncio.get_event_loop().time() < end_time:
                try:
                    msg = await asyncio.wait_for(ws.receive(), timeout=1)
                    if msg.type == aiohttp.WSMsgType.TEXT:
                        data = json.loads(msg.data)
                        if isinstance(data, list):
                            for item in data:
                                if item.get("ev") == "OT":
                                    trade_count += 1
                                    print_flush(f"TRADE {trade_count}: {item}")
                                else:
                                    print_flush(f"MESSAGE: {item}")
                        else:
                            print_flush(f"DATA: {data}")
                except asyncio.TimeoutError:
                    # Just a timeout in wait_for, continue the loop
                    print(".", end="", flush=True)
                    sys.stdout.flush()
            
            print_flush(f"\nTest complete. Received {trade_count} trades.")

if __name__ == "__main__":
    print_flush("Starting Polygon WebSocket Simple Test")
    print_flush("Will listen for 60 seconds for any SPX option trades...")
    print_flush("Polygon documentation: https://polygon.io/docs/options/ws_options_trades")
    
    # Print your API key type/level to verify
    api_key = os.environ.get("POLYGON_KEY", "")
    key_start = api_key[:4] if len(api_key) > 4 else ""
    key_end = api_key[-4:] if len(api_key) > 4 else ""
    print_flush(f"Using API key: {key_start}...{key_end}")
    
    try:
        asyncio.run(test_polygon())
    except KeyboardInterrupt:
        print_flush("\nTest stopped by user")
    except Exception as e:
        print_flush(f"Error: {type(e).__name__}: {e}")