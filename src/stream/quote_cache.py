# src/stream/quote_cache.py
import os, asyncio, datetime, aiohttp
from collections import defaultdict
from dotenv import load_dotenv
from src.data.contract_loader import todays_spx_0dte_contracts
from pathlib import Path
from src.stream import polygon_client

load_dotenv()
API_KEY = os.getenv("POLYGON_KEY")
BASE    = "https://api.polygon.io"

quotes = {}   # Global dict that will store the latest quotes

try:
    _UNIVERSE = todays_spx_0dte_contracts(Path("data/snapshots"))
except Exception as e:
    print(f"Warning: Could not load contracts from snapshot: {e}")
    _UNIVERSE = []  # Empty list as fallback

async def _today_spxw_symbols(session) -> list[str]:
    """Return all SPXW contracts expiring today."""
    today = datetime.date.today().isoformat()
    url   = f"{BASE}/v3/reference/options/contracts"
    params = {"underlying_ticker": "SPX", "expiration_date": today,
              "limit": 1000, "apiKey": API_KEY}
    async with session.get(url, params=params, timeout=10) as r:
        r.raise_for_status()
        data = await r.json()
    return [item["ticker"] for item in data.get("results", [])]

async def run(poll_ms: int = 250):
    """
    Concurrent poller: ≤50 in-flight /v3/quotes requests.
    Fills the module-level `quotes` dict that tests assert on.
    """
    symbols = _UNIVERSE
    if not symbols:
        raise RuntimeError("no 0-DTE symbols in snapshot")

    print(f"Starting quote cache for {len(symbols)} contracts")

    sem = asyncio.Semaphore(50)              # 50 rps → 3 000 rpm

    async with aiohttp.ClientSession() as sess:
        async def bound_fetch(sym: str):
            async with sem:
                q = await polygon_client.fetch_quote(sess, sym)
                if q:
                    quotes[sym] = (q["last_quote"]["bid_price"],
                                   q["last_quote"]["ask_price"],
                                   q["last_quote"]["sip_timestamp"])

        while True:
            # launch one coroutine per symbol, limited by the semaphore
            await asyncio.gather(*(bound_fetch(s) for s in symbols))
            await asyncio.sleep(poll_ms / 1000)