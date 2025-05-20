import os, aiohttp, asyncio, json, websocket  # websocket-client pkg
from typing import Any

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
def make_ws(url: str) -> websocket.WebSocket:
    """
    Open a Polygon websocket, perform auth handshake, and return the live
    socket ready for subscribe() calls.
    """
    ws = websocket.create_connection(url, ping_interval=30, ping_timeout=10)

    # --- send auth frame ----------------------------------------------------
    ws.send(json.dumps({"action": "auth", "params": _API_KEY}))

    # Polygon sends one or more status frames:
    #   1) {'status':'connected',     …}
    #   2) {'status':'auth_success',  …}
    # Loop until we see auth_success or an explicit auth_failed
    while True:
        raw   = ws.recv()
        frame = json.loads(raw)
        if isinstance(frame, list):
            frame = frame[0] if frame else {}

        st = frame.get("status")
        if st == "auth_success":
            return ws            # ← all good
        if st == "auth_failed":
            raise RuntimeError(f"Polygon WS auth failed: {frame}")
        # otherwise (e.g. 'connected') just keep reading