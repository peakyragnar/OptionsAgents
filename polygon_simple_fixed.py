"""
Fixed version of the Polygon WebSocket client focused on the proper params format.
"""

import os
import asyncio
import json
import aiohttp
import time
import sys
from dotenv import load_dotenv
load_dotenv()

# Print with flush
def print_flush(msg):
    print(msg, flush=True)
    sys.stdout.flush()

async def monitor_trades():
    """Connect to Polygon WebSocket and log all messages received."""
    # Get API key from environment
    api_key = os.environ.get("POLYGON_KEY", "DUMMY_KEY")
    
    # Connect to Polygon WebSocket for options
    url = f"wss://socket.polygon.io/options?apiKey={api_key}"
    
    print_flush(f"Connecting to {url}")
    start_time = time.time()
    trade_count = 0
    
    async with aiohttp.ClientSession() as session:
        async with session.ws_connect(url, heartbeat=30, timeout=60) as ws:
            print_flush("Connected to WebSocket")
            
            # Send authentication
            auth_msg = {"action": "auth", "params": api_key}
            print_flush(f"Sending auth message: {auth_msg}")
            await ws.send_json(auth_msg)
            
            # Wait for auth response
            auth_resp = await ws.receive()
            print_flush(f"Auth response: {auth_resp.data if auth_resp.type == aiohttp.WSMsgType.TEXT else auth_resp}")
            
            # Sample test symbols
            test_symbols = [
                "O:SPX240520C04800000",
                "O:SPX240520P04800000",
                "O:SPX240520C04900000",
                "O:SPX240520P04900000",
                "O:SPX240520C05000000",
                "O:SPX240520P05000000",
            ]
            
            # CRITICAL FIX: Use an array of strings for the params
            formatted_symbols = [f"OT.{symbol}" for symbol in test_symbols]
            sub_msg = {"action": "subscribe", "params": formatted_symbols}
            
            print_flush(f"Sending subscription message with ARRAY format: {json.dumps(sub_msg)}")
            await ws.send_json(sub_msg)
            
            # Also try a wildcard subscription
            wildcard_msg = {"action": "subscribe", "params": ["OT.*"]}
            print_flush(f"Sending wildcard subscription: {json.dumps(wildcard_msg)}")
            await ws.send_json(wildcard_msg)
            
            # Wait for subscription response
            sub_resp = await ws.receive()
            print_flush(f"Subscription response: {sub_resp.data if sub_resp.type == aiohttp.WSMsgType.TEXT else sub_resp}")
            
            # Listen for 60 seconds
            print_flush("Listening for trade messages for 60 seconds...")
            end_time = start_time + 60
            
            while time.time() < end_time:
                try:
                    msg = await asyncio.wait_for(ws.receive(), timeout=1)
                    if msg.type == aiohttp.WSMsgType.TEXT:
                        data = json.loads(msg.data)
                        print_flush(f"Received message: {msg.data[:100]}...")
                        
                        if isinstance(data, list):
                            for item in data:
                                if isinstance(item, dict) and item.get("ev") == "OT":
                                    trade_count += 1
                                    print_flush(f"TRADE #{trade_count}: {item}")
                except asyncio.TimeoutError:
                    # Just a heartbeat/timeout
                    seconds_left = int(end_time - time.time())
                    if seconds_left % 5 == 0:  # Print every 5 seconds
                        print_flush(f"Still listening... {seconds_left} seconds left, {trade_count} trades so far")
            
            print_flush(f"Test complete. Total trades: {trade_count}")

if __name__ == "__main__":
    print_flush(f"Starting Polygon WebSocket test with FIXED subscription format")
    print_flush(f"Testing with options WebSocket")
    print_flush("Press Ctrl+C to exit")
    
    try:
        asyncio.run(monitor_trades())
    except KeyboardInterrupt:
        print_flush("\nTest stopped by user")
    except Exception as e:
        print_flush(f"Error: {type(e).__name__}: {e}")