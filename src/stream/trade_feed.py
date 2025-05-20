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
def _ws_url(symbols: list[str], delayed: bool) -> str:
    root = "wss://delayed.polygon.io" if delayed else "wss://socket.polygon.io"
    syms = ",".join(symbols)
    return f"{root}/options?apiKey={_KEY}&symbols={syms}"

async def run(symbols: list[str], *, delayed: bool = False) -> None:
    """
    Start a websocket connection for *symbols* and push trade dictionaries
    into TRADE_Q forever (reconnects on drops).
    """
    url = _ws_url(symbols, delayed)
    while True:
        try:
            async with aiohttp.ClientSession() as sess:
                async with sess.ws_connect(url, heartbeat=30) as ws:
                    async for msg in ws:
                        if msg.type is aiohttp.WSMsgType.TEXT:
                            for trade in json.loads(msg.data):
                                await TRADE_Q.put(trade)
                        elif msg.type == aiohttp.WSMsgType.ERROR:
                            raise ws.exception()
        except Exception as exc:
            # Back-off on errors
            print(f"[trade_feed] {type(exc).__name__}: {exc}; reconnecting…")
            await asyncio.sleep(3)