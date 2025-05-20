#!/usr/bin/env python
"""
Working test for Polygon.io WebSocket option trades subscription.
Based on proven working example.
"""
import asyncio
import json
import os
import aiohttp
import datetime as dt
from dotenv import load_dotenv
load_dotenv()

# Configuration
API_KEY = os.environ.get("POLYGON_KEY", "")
URL = f"wss://socket.polygon.io/options?apiKey={API_KEY}"

# Test both specific symbols and wildcard
TEST_SYMBOLS = [
    "O:SPX250520C05000000",
    "O:SPX250520P05000000",
    "O:SPX250520C04900000",
    "O:SPX250520P04900000"
]

async def main():
    print(f"Connecting to {URL}")
    
    async with aiohttp.ClientSession() as session:
        async with session.ws_connect(URL, heartbeat=30) as ws:
            print("Connected to WebSocket")
            
            # Authenticate
            await ws.send_json({"action": "auth", "params": API_KEY})
            auth_resp = await ws.receive()
            print(f"Auth response: {auth_resp.data}")
            
            # Format the symbols correctly for subscription
            formatted_symbols = [f"T.{symbol}" for symbol in TEST_SYMBOLS]
            
            # Subscribe to specific symbols
            print(f"Subscribing to specific symbols: {formatted_symbols}")
            await ws.send_json({"action": "subscribe", "params": formatted_symbols})
            specific_resp = await ws.receive()
            print(f"Specific symbols response: {specific_resp.data}")
            
            # Also subscribe to all option trades as wildcard
            print("Subscribing to all option trades with wildcard")
            await ws.send_json({"action": "subscribe", "params": ["T.O:*"]})
            wildcard_resp = await ws.receive()
            print(f"Wildcard response: {wildcard_resp.data}")
            
            # Listen for trades
            count = 0
            spx_count = 0
            start = dt.datetime.utcnow()
            print("\nListening for trades for 30 seconds...")
            
            while (dt.datetime.utcnow() - start).seconds < 30:
                try:
                    msg = await asyncio.wait_for(ws.receive(), timeout=1)
                    if msg.type == aiohttp.WSMsgType.TEXT:
                        data = json.loads(msg.data)
                        
                        # Extract trades from the message
                        trades = [d for d in data if d.get("ev") == "T"]
                        
                        if trades:
                            count += len(trades)
                            
                            # Count SPX trades separately
                            spx_trades = [t for t in trades if "SPX" in t.get("sym", "")]
                            spx_count += len(spx_trades)
                            
                            # Print sample trades (limit to first 5)
                            if count <= 5:
                                print(f"\nSample trade {count}:")
                                print(json.dumps(trades[0], indent=2))
                            
                            # Just print a counter for the rest
                            else:
                                seconds = (dt.datetime.utcnow() - start).seconds
                                print(f"\rReceived {count} total trades ({spx_count} SPX trades) in {seconds}s", end="")
                except asyncio.TimeoutError:
                    # Just for a heartbeat/status
                    seconds = (dt.datetime.utcnow() - start).seconds
                    if seconds % 5 == 0:
                        print(f"\rListening... {30-seconds}s remaining, {count} trades so far", end="")
            
            print(f"\n\nTest complete. Received {count} total trades ({spx_count} SPX trades) in 30 seconds.")

if __name__ == "__main__":
    print("Running working Polygon.io WebSocket test")
    print("Using correct T.O: format for option trades")
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nTest stopped by user")
    except Exception as e:
        print(f"Error: {type(e).__name__}: {e}")