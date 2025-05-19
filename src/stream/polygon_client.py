import os, aiohttp, asyncio

_BASE = "https://api.polygon.io/v3/quotes/{}"
_API_KEY = os.environ["POLYGON_KEY"]

async def fetch_quote(sess: aiohttp.ClientSession, occ_ticker: str):
    url = _BASE.format(occ_ticker)
    params = {"limit": 1, "apiKey": _API_KEY}
    async with sess.get(url, params=params, timeout=10) as r:
        r.raise_for_status()
        js = await r.json()
        return js["results"][0] if js.get("results") else None