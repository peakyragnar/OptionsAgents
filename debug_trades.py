"""
Simple script to monitor Polygon.io options trade WebSocket without any other components.
Purely for debugging trade data flow.
"""

import os
import asyncio
import json
import aiohttp
import time
import sys
from dotenv import load_dotenv
load_dotenv()

# Print with flush to ensure we see output immediately
def print_flush(msg):
    print(msg, flush=True)
    sys.stdout.flush()

async def monitor_trades():
    """Connect to Polygon WebSocket and log all messages received."""
    # Get API key from environment
    api_key = os.environ.get("POLYGON_KEY", "DUMMY_KEY")
    
    # Use delayed endpoint if testing
    use_delayed = False
    root = "wss://delayed.polygon.io" if use_delayed else "wss://socket.polygon.io"
    url = f"{root}/options?apiKey={api_key}"
    
    # Sample test symbols (SPX options)
    test_symbols = [
        "O:SPX240520C04800000",
        "O:SPX240520P04800000",
        "O:SPX240520C04900000",
        "O:SPX240520P04900000",
        "O:SPX240520C05000000",
        "O:SPX240520P05000000",
    ]
    
    print_flush(f"Connecting to {url}")
    print_flush(f"Using {len(test_symbols)} test symbols")
    
    try:
        print_flush("Creating client session...")
        async with aiohttp.ClientSession() as session:
            print_flush("Opening WebSocket connection...")
            async with session.ws_connect(url, heartbeat=30, timeout=60) as ws:
                print_flush("Connected to Polygon WebSocket")
                
                # Send authentication
                print_flush("Authenticating...")
                await ws.send_json({"action": "auth", "params": api_key})
                print_flush("Authentication request sent")
                
                # Wait for auth response
                print_flush("Waiting for auth response...")
                auth_resp = await ws.receive()
                print_flush(f"Received: {auth_resp}")
                if auth_resp.type == aiohttp.WSMsgType.TEXT:
                    print_flush(f"Auth response data: {auth_resp.data}")
                
                # Subscribe to trades for test symbols
                print_flush("Subscribing to option trades...")
                
                # Try method 1: traditional Polygon format (list of prefixed symbols)
                formatted_symbols = [f"OT.{sym}" for sym in test_symbols]
                sub_request1 = {"action": "subscribe", "params": formatted_symbols}
                print_flush(f"Subscription request 1: {json.dumps(sub_request1)}")
                await ws.send_json(sub_request1)
                print_flush("Method 1: Subscribed with list of prefixed symbols")
                
                # Wait for subscription response
                print_flush("Waiting for subscription response...")
                sub_resp = await ws.receive()
                print_flush(f"Received: {sub_resp}")
                if sub_resp.type == aiohttp.WSMsgType.TEXT:
                    print_flush(f"Subscription response data: {sub_resp.data}")
                
                # Listen for messages
                print_flush("Listening for messages...")
                print_flush("==================================================")
                trade_count = 0
                message_count = 0
                
                # Create a timeout for listening (30 seconds)
                start_time = time.time()
                timeout = 30  # seconds
                
                while time.time() - start_time < timeout:
                    print_flush(f"Waiting for message {message_count+1}...")
                    msg = await asyncio.wait_for(ws.receive(), timeout=5)
                    message_count += 1
                    
                    if msg.type == aiohttp.WSMsgType.TEXT:
                        print_flush(f"Received text message: {msg.data[:200]}...")
                        data = json.loads(msg.data)
                        
                        # Print summary for each message
                        print_flush(f"Message {message_count}, {trade_count} trades so far")
                        
                        # Print the full message for detailed analysis
                        if isinstance(data, list) and data:
                            for item in data:
                                if isinstance(item, dict):
                                    if item.get("ev") == "OT":
                                        trade_count += 1
                                        print_flush(f"TRADE: {item}")
                                    else:
                                        print_flush(f"MESSAGE: {item}")
                        else:
                            print_flush(f"DATA: {data}")
                    
                    elif msg.type == aiohttp.WSMsgType.ERROR:
                        print_flush(f"WebSocket error: {ws.exception()}")
                        break
                    elif msg.type == aiohttp.WSMsgType.CLOSED:
                        print_flush("WebSocket connection closed")
                        break
                
                print_flush(f"Monitoring complete. Received {message_count} messages, {trade_count} trades")
    except Exception as e:
        print(f"Error: {type(e).__name__}: {e}")

if __name__ == "__main__":
    print("Starting Polygon.io WebSocket Trade Monitor")
    print("Press Ctrl+C to exit")
    try:
        asyncio.run(monitor_trades())
    except KeyboardInterrupt:
        print("\nMonitoring stopped by user")