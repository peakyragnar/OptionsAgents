"""
quote_cache.py
--------------
Populate a module-level `quotes` dict with NBBOs for every same-day (0-DTE)
SPX / SPXW contract.  Designed so that tests/test_quote_cache.py sees a
non-empty dict inside two seconds.

Prerequisites
* POLYGON_KEY exported in the shell.
* A Parquet snapshot  data/snapshots/spx_contracts_YYYYMMDD.parquet
  written by your existing snapshot job.
"""

from __future__ import annotations
import asyncio, datetime, os
from pathlib import Path

import aiohttp

# discover contracts only when the poller starts
from src.data.contract_loader import todays_spx_0dte_contracts
from . import polygon_client


# --------------------------------------------------------------------- #
# 1.  build universe once                                               #
# --------------------------------------------------------------------- #

_SNAPSHOT_DIR = Path("data/snapshots")
# will be populated the first time run() is called
_UNIVERSE: list[str] | None = None


# --------------------------------------------------------------------- #
# 2.  public cache – tests read this                                    #
# --------------------------------------------------------------------- #

# key   = OCC ticker e.g. 'O:SPXW250519P05000000'
# value = (bid_price, ask_price, sip_timestamp)
quotes: dict[str, tuple[float, float, int]] = {}


# --------------------------------------------------------------------- #
# 3.  helpers                                                           #
# --------------------------------------------------------------------- #

async def _fetch_and_store(
    sem: asyncio.Semaphore,
    sess: aiohttp.ClientSession,
    sym: str,
) -> None:
    """Rate-limited fetch; save NBBO straight into `quotes`."""
    async with sem:
        try:
            q = await polygon_client.fetch_quote(sess, sym)
        except Exception:
            return                    # network error / 5xx / timeout
        if q:
            quotes[sym] = (
                q["bid_price"],
                q["ask_price"],
                q["sip_timestamp"],
            )


# --------------------------------------------------------------------- #
# 4.  poller                                                            #
# --------------------------------------------------------------------- #

async def run(poll_ms: int = 250, max_concurrency: int = 50) -> None:
    """
    Refresh all NBBOs forever.

    * poll_ms         – delay between full passes (default 250 ms).
    * max_concurrency – keep ≤ this many HTTP requests in flight
                        (Polygon Advanced tier allows 50 rps).
    """
    global _UNIVERSE

    # -----------------------------------------------------------------
    # build universe on first entry
    # -----------------------------------------------------------------
    if _UNIVERSE is None:
        _UNIVERSE = todays_spx_0dte_contracts(_SNAPSHOT_DIR)

        if not _UNIVERSE:                       # snapshot missing ⇒ REST fallback
            async def _polygon_universe() -> list[str]:
                url = "https://api.polygon.io/v3/reference/options/contracts"
                today = datetime.date.today().isoformat()
                params = {
                    "underlying_ticker": "SPX",
                    "expiration_date":   today,
                    "limit":             1000,
                    "apiKey":            os.environ["POLYGON_KEY"],
                }
                async with aiohttp.ClientSession() as s:
                    async with s.get(url, params=params, timeout=10) as r:
                        r.raise_for_status()
                        js = await r.json()
                        return [c["ticker"] for c in js.get("results", [])]

            _UNIVERSE = await _polygon_universe()

        if not _UNIVERSE:
            raise RuntimeError("quote_cache: no 0-DTE SPX symbols available.")

        print(f"quote_cache: tracking {len(_UNIVERSE)} contracts")

    sem = asyncio.Semaphore(max_concurrency)

    async with aiohttp.ClientSession() as sess:
        while True:
            tasks = [_fetch_and_store(sem, sess, s) for s in _UNIVERSE]

            # handle each quote as soon as its request completes
            for fut in asyncio.as_completed(tasks):
                await fut

            await asyncio.sleep(poll_ms / 1000)