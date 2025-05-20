"""
Simplified WebSocket client for Polygon.io options data.
"""
import os, json, asyncio, ssl
from collections import defaultdict
import websockets
from dotenv import load_dotenv

load_dotenv()

# Configuration
API_KEY = os.getenv("POLYGON_KEY")
WS_URL = "wss://socket.polygon.io/options"  # Real-time socket for options data

# Messages
AUTH_MSG = json.dumps({"action": "auth", "params": API_KEY})
STOCKS_SUB = json.dumps({"action": "subscribe", "params": "T.AAPL"})  # Just subscribe to AAPL trades

# Data stores
quotes = {}
pos_long = defaultdict(int)
pos_short = defaultdict(int)

async def stream_stocks():
    """Try connecting to stocks endpoint as a test."""
    print(f"Connecting to stocks endpoint: {STOCKS_URL}")
    ssl_ctx = ssl.create_default_context()
    
    try:
        async with websockets.connect(STOCKS_URL, ssl=ssl_ctx) as ws:
            print("Connected to stocks endpoint")
            await ws.send(AUTH_MSG)
            
            # Process auth response
            resp = await ws.recv()
            print(f"Auth response: {resp}")
            
            # Send subscription
            await ws.send(STOCKS_SUB)
            
            # Process subscription response
            resp = await ws.recv()
            print(f"Subscription response: {resp}")
            
            # Process messages
            count = 0
            async for msg in ws:
                count += 1
                print(f"Message #{count}: {msg[:100]}...")
                if count >= 10:
                    print("Received 10 messages, exiting")
                    break
                    
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    print("Running simplified test client")
    print(f"API_KEY starts with: {API_KEY[:5]}...")
    asyncio.run(stream_stocks())