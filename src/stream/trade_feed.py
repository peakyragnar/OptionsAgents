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

# Import quotes from quote_cache to filter trades
from src.stream.quote_cache import quotes

TRADE_Q: Final[asyncio.Queue[dict]] = asyncio.Queue(maxsize=20_000)
_KEY = os.environ.get("POLYGON_KEY", "DUMMY_KEY")      # tests patch this

# Helper builds the websocket URL
def _ws_url(delayed: bool) -> str:
    root = "wss://delayed.polygon.io" if delayed else "wss://socket.polygon.io"
    return f"{root}/options"     # key no longer in URL

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
                    
                    # 1) authenticate
                    await ws.send_json({"action": "auth", "params": _KEY})
                    
                    # Look for debug environment variable to print symbols
                    if os.environ.get("OA_DEBUG"):
                        print(f"[trade_feed] Symbols to subscribe [{len(symbols)}]: {symbols[:5]}...")
                    
                    # 2) subscribe to trades in ≤100-symbol chunks
                    CHUNK = 100  # max tickers per message
                    for i in range(0, len(symbols), CHUNK):
                        batch = [f"T.{sym}" for sym in symbols[i:i+CHUNK]]
                        
                        print(f"[trade_feed] Subscribing to chunk {i//CHUNK + 1}/{(len(symbols)-1)//CHUNK + 1} with {len(batch)} symbols")
                        
                        # Send subscription message
                        await ws.send_json({"action": "subscribe",
                                           "params": ",".join(batch)})   # Polygon wants a string
                        print(f"[trade_feed] Subscription request sent")
                        
                        # Add a small delay between subscription batches
                        await asyncio.sleep(0.5)
                    
                    # FALLBACK: Subscribe to all option trades as a wildcard
                    print("[trade_feed] Adding wildcard subscription for all option trades")
                    wildcard_sub = {"action": "subscribe", "params": "T.*"}   # Polygon wants a string
                    await ws.send_json(wildcard_sub)
                    print("[trade_feed] All option trades wildcard subscription sent")
                    
                    # Reset backoff after successful connection
                    backoff = 1
                    
                    # Process messages
                    async for msg in ws:
                        if msg.type is aiohttp.WSMsgType.TEXT:
                            data = json.loads(msg.data)
                            
                            # Enhanced debugging - print all message types with more details
                            if isinstance(data, dict):
                                print(f"[trade_feed] Received dict message: {data.keys()}")
                                # Print the entire dict for debugging
                                print(f"[trade_feed] FULL DICT: {json.dumps(data)}")
                            elif isinstance(data, list) and data:
                                if len(data) > 0:
                                    key_info = data[0].keys() if isinstance(data[0], dict) and data[0] else 'empty'
                                    print(f"[trade_feed] Received list message [{len(data)} items]: {key_info}")
                                    
                                    # Print the first item in full for debugging
                                    if isinstance(data[0], dict):
                                        print(f"[trade_feed] SAMPLE LIST ITEM: {json.dumps(data[0])}")
                                else:
                                    print(f"[trade_feed] Received empty list message")
                            else:
                                print(f"[trade_feed] Received unknown message type: {type(data)}")
                                print(f"[trade_feed] RAW DATA: {data}")
                            
                            # Check if it's a trade message (list of trades)
                            if isinstance(data, list) and data:
                                # Trade frames:  {"ev":"T", "sym": ... }
                                if data[0].get("ev") == "T" and data[0].get("sym"):
                                    print(f"[trade_feed] Processing {len(data)} trade messages")
                                    for trade in data:
                                        # Only process valid trade messages
                                        if trade.get('ev') == 'T' and trade.get('sym') and trade.get('p') and trade.get('s'):
                                            symbol = trade.get('sym')
                                            print(f"[trade_feed] Trade: {symbol} {trade.get('s')}@{trade.get('p')}")
                                            # Only forward trades for symbols we already track NBBO for
                                            if symbol in quotes:
                                                await TRADE_Q.put(trade)
                                            else:
                                                print(f"[trade_feed] Skipping trade for {symbol} (no NBBO data)"
                                # Handle status messages in list format
                                elif 'status' in data[0]:
                                    print(f"[trade_feed] Status in list: {data[0].get('status')} - {data[0].get('message', '')}")
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