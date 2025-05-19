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
    """Continuously refresh bids/asks for today's weeklies."""
    # Use pre-loaded universe if available, otherwise fetch from API
    if not _UNIVERSE:
        async with aiohttp.ClientSession() as session:
            symbols = await _today_spxw_symbols(session)
            if not symbols:
                raise RuntimeError("No SPX tickers available for today")
    else:
        symbols = _UNIVERSE
    
    print(f"Starting quote cache for {len(symbols)} contracts")
    
    async with aiohttp.ClientSession() as sess:
        while True:
            for tkr in symbols:
                q = await polygon_client.fetch_quote(sess, tkr)
                if q and "last_quote" in q:
                    quotes[tkr] = (q["last_quote"]["bid"], q["last_quote"]["ask"], q["last_quote"]["sip_timestamp"])
            
            print(f"Updated {len(quotes)} quotes")
            await asyncio.sleep(0.25)  # ~4 Hz per contract – tune as needed