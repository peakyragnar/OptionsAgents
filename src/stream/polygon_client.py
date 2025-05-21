import os, aiohttp, asyncio, json, websocket, ssl, time, logging  # websocket-client pkg
from typing import Any

def _first_dict(msg):
    """Polygon wraps every control frame in a 1-element list; unwrap it."""
    if isinstance(msg, list):
        return msg[0] if msg else {}
    return msg

_BASE = "https://api.polygon.io/v3/quotes/{}"
_API_KEY = os.environ["POLYGON_KEY"]

async def fetch_quote(sess: aiohttp.ClientSession, occ_ticker: str):
    url = _BASE.format(occ_ticker)
    params = {"limit": 1, "apiKey": _API_KEY}
    async with sess.get(url, params=params, timeout=10) as r:
        r.raise_for_status()
        js = await r.json()
        return js["results"][0] if js.get("results") else None


# --------------------------------------------------------------------------- #
def make_ws(url: str):
    ws = websocket.create_connection(url, ping_interval=30)

    # 1️⃣  initial "connected" frame ----------------------------------------
    raw = ws.recv()
    print("RAW FRAME-1:", raw)          #  <<––-- add this
    frame = _first_dict(json.loads(raw))
    if frame.get("status") != "connected":
        raise RuntimeError(f"Polygon WS handshake failed: {frame}")

    # 2️⃣  send auth --------------------------------------------------------
    api_key = (
        os.getenv("POLYGON_API_KEY")    # most common var name
        or os.getenv("POLYGON_KEY")     # legacy name used elsewhere
    )
    if not api_key:
        raise RuntimeError("POLYGON_API_KEY env-var not set")
    ws.send(json.dumps({"action": "auth", "params": api_key}))

    # 3️⃣  expect auth_success ---------------------------------------------
    raw = ws.recv()
    print("RAW FRAME-2:", raw)          #  <<––-- add this
    frame = _first_dict(json.loads(raw))
    if frame.get("status") != "auth_success":
        raise RuntimeError(f"Polygon WS auth failed: {frame}")

    return ws