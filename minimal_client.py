#!/usr/bin/env python
"""
Absolutely minimal WebSocket client for Polygon.io options feed.
Just connects and prints every raw message received.
"""
import os, json, asyncio, websockets, ssl
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv("POLYGON_KEY")
WS_URL = "wss://socket.polygon.io/options"  # Correct endpoint for options data

async def run():
    print(f"Connecting to {WS_URL}")
    ssl_ctx = ssl.create_default_context()
    
    async with websockets.connect(WS_URL, ssl=ssl_ctx) as ws:
        # Authenticate
        print("Sending authentication...")
        auth_msg = json.dumps({"action": "auth", "params": API_KEY})
        await ws.send(auth_msg)
        
        # Wait for auth response
        resp = await ws.recv()
        print(f"Auth response: {resp}")
        
        # Subscribe to stock data
        print("Subscribing to stock data...")
        for channel in ["T.SPY", "Q.SPY", "T.AAPL", "Q.AAPL"]:
            await ws.send(json.dumps({"action": "subscribe", "params": channel}))
            resp = await ws.recv()
            print(f"Subscription response for {channel}: {resp}")
        
        # Just print every message received
        print("\nNow printing all raw messages received:")
        print("=======================================")
        count = 0
        start_time = asyncio.get_event_loop().time()
        
        while True:
            try:
                raw = await asyncio.wait_for(ws.recv(), timeout=1.0)
                count += 1
                elapsed = asyncio.get_event_loop().time() - start_time
                print(f"[{elapsed:.1f}s] MSG #{count}: {raw}")
                
                # Also print every 10 seconds how many messages we've received
                if int(elapsed) % 10 == 0 and int(elapsed) > 0:
                    print(f"\n=== SUMMARY AFTER {int(elapsed)} SECONDS ===")
                    print(f"Total messages received: {count}")
                    print("=======================================\n")
                    
            except asyncio.TimeoutError:
                elapsed = asyncio.get_event_loop().time() - start_time
                if elapsed > 30:
                    print(f"\nNo messages for 30 seconds. Received {count} total messages.")
                    if count == 0:
                        print("NO DATA RECEIVED - Please check your account access or try during market hours.")
                    break

if __name__ == "__main__":
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        print("\nClient terminated by user")
    except Exception as e:
        print(f"Error: {e}")