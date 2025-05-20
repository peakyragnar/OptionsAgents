"""
trade_feed.py
-------------
Connects to Polygon's options trade websocket and streams messages into
TRADE_Q.  A higher-level engine (dealer/engine.py) will consume the queue.

Public API
----------
TRADE_Q : asyncio.Queue[dict]
run(symbols: list[str], *, delayed: bool = False) -> Coroutine
"""

from __future__ import annotations
import asyncio, json, os, aiohttp, datetime as _dt
from typing import Final

TRADE_Q: Final[asyncio.Queue[dict]] = asyncio.Queue(maxsize=20_000)
_KEY = os.environ.get("POLYGON_KEY", "DUMMY_KEY")      # tests patch this

# Helper builds the websocket URL
def _ws_url(delayed: bool) -> str:
    root = "wss://delayed.polygon.io" if delayed else "wss://socket.polygon.io"
    return f"{root}/options?apiKey={_KEY}"

async def run(symbols: list[str], *, delayed: bool = False) -> None:
    """
    Start a websocket connection for *symbols* and push trade dictionaries
    into TRADE_Q forever (reconnects on drops).
    """
    url = _ws_url(delayed)
    backoff = 1  # Initial backoff in seconds
    max_backoff = 30  # Maximum backoff in seconds
    
    while True:
        try:
            async with aiohttp.ClientSession() as sess:
                # Increase timeout and heartbeat settings to help prevent disconnections
                async with sess.ws_connect(url, heartbeat=30, timeout=60) as ws:
                    print(f"[trade_feed] Connected to {url}")
                    
                    # Send auth message first
                    await ws.send_json({"action": "auth", "params": _KEY})
                    
                    # subscribe in chunks of 50 tickers or less (smaller chunks)
                    CHUNK = 50
                    for i in range(0, len(symbols), CHUNK):
                        batch = symbols[i : i + CHUNK]
                        sub_msg = {"action": "subscribe", "params": f"OT.{',OT.'.join(batch)}"}
                        await ws.send_json(sub_msg)
                        print(f"[trade_feed] Subscribed to chunk {i//CHUNK + 1}/{(len(symbols)-1)//CHUNK + 1}")
                        # Add a small delay between subscription batches
                        await asyncio.sleep(0.5)
                    
                    # Reset backoff after successful connection
                    backoff = 1
                    
                    # Process messages
                    async for msg in ws:
                        if msg.type is aiohttp.WSMsgType.TEXT:
                            data = json.loads(msg.data)
                            # Check if it's a status message
                            if isinstance(data, list) and data and 'ev' in data[0]:
                                for trade in data:
                                    await TRADE_Q.put(trade)
                            # Handle connection status messages for debugging
                            elif isinstance(data, dict) and 'status' in data:
                                print(f"[trade_feed] Status: {data.get('status')} - {data.get('message', '')}")
                        elif msg.type == aiohttp.WSMsgType.ERROR:
                            print(f"[trade_feed] WebSocket error: {ws.exception()}")
                            raise ws.exception()
                        elif msg.type == aiohttp.WSMsgType.CLOSED:
                            print("[trade_feed] Connection closed")
                            break
        except asyncio.CancelledError:
            # Allow clean task cancellation
            raise
        except Exception as exc:
            # Implement exponential backoff
            print(f"[trade_feed] {type(exc).__name__}: {exc}; reconnecting in {backoff}s...")
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, max_backoff)  # Exponential backoff with ceiling