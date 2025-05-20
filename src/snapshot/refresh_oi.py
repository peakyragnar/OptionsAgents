#!/usr/bin/env python
"""
refresh_oi.py
-------------
Download end-of-day open-interest (OI) for a list of underlyings and save it as a
Parquet snapshot.  The dealer-gamma tool uses this file as the baseline
inventory that dealers carry into the current trading session.

Usage (from project root)
------------------------
python -m src.snapshot.refresh_oi --symbols SPY QQQ            # yesterday's OI
python -m src.snapshot.refresh_oi --symbols SPY --date 2024-05-17

Environment
-----------
POLYGON_API_KEY   – required.  Free/paid Polygon key that has the options/OI endpoint.
DATA_DIR          – optional.  Root directory where snapshots are stored.  Defaults to
                    ./data/oi/<date>/<symbol>_oi.parquet

The script is intentionally dependency-light (pandas + requests) and portable.
If you pull OI from another vendor (OCC FTP, Quandl, OPRA files, etc.) just
swap-out the `fetch_polygon_oi` function.
"""

from __future__ import annotations

import argparse
import datetime as dt
import os
from pathlib import Path
from typing import Iterable, List

import pandas as pd
import requests

###############################################################################
# Config
###############################################################################

POLYGON_API_KEY: str | None = os.getenv("POLYGON_API_KEY")
if not POLYGON_API_KEY:
    raise RuntimeError(
        "POLYGON_API_KEY env-var not set – required for options OI endpoint"
    )

DATA_DIR = Path(os.getenv("DATA_DIR", "data")) / "oi"
DATA_DIR.mkdir(parents=True, exist_ok=True)

###############################################################################
# Helpers
###############################################################################


def _as_of(date_str: str | None) -> str:
    """Return the ISO-date we need (defaults to *yesterday*)."""
    if date_str:
        return dt.date.fromisoformat(date_str).isoformat()
    return (dt.date.today() - dt.timedelta(days=1)).isoformat()


def fetch_polygon_oi(underlying: str, date: str) -> pd.DataFrame:
    """Call Polygon v3 reference OI endpoint and return a tidy DataFrame."""

    # Hot-fix: Use the correct endpoint URL format
    url = (
        "https://api.polygon.io/v3/reference/options/open-interest"
        f"?symbol={underlying}&date={date}"
        f"&limit=50000&apiKey={POLYGON_API_KEY}"
    )
    
    resp = requests.get(url, timeout=20)
    resp.raise_for_status()
    records = resp.json()["results"]

    if not records:
        raise RuntimeError(f"No OI data returned for {underlying} on {date}")

    df = pd.DataFrame.from_records(records)
    # Normalise / rename for downstream consumers
    df = (
        df.rename(
            columns={
                "ticker": "option_symbol",
                "exp_date": "expiry",
                "strike_price": "strike",
                "type": "call_put",
            }
        )[
            [
                "option_symbol",
                "expiry",
                "strike",
                "call_put",
                "open_interest",
            ]
        ]
        .assign(symbol=underlying, snapshot_date=date)
    )

    # Dtypes – keep memory footprint sane
    df["open_interest"] = df["open_interest"].astype("int64")
    df["strike"] = df["strike"].astype("float64")
    df["call_put"] = df["call_put"].astype("category")

    return df


def save_snapshot(df: pd.DataFrame, underlying: str, date: str) -> Path:
    out_dir = DATA_DIR / date
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{underlying}_oi.parquet"
    df.to_parquet(path, index=False)
    return path


def refresh(symbols: Iterable[str], date: str) -> None:
    for sym in symbols:
        print(f"[refresh_oi] Fetching {sym} OI for {date} …", flush=True)
        df = fetch_polygon_oi(sym, date)
        out_path = save_snapshot(df, sym, date)
        print(f"[refresh_oi]  ↳ {len(df):,} rows → {out_path}")


###############################################################################
# CLI
###############################################################################


def main() -> None:
    parser = argparse.ArgumentParser(description="Refresh EOD Open-Interest snapshots.")
    parser.add_argument(
        "--symbols",
        nargs="+",
        required=True,
        help="Underlying tickers (e.g. SPY QQQ)",
    )
    parser.add_argument(
        "--date",
        help="ISO date string (default: yesterday – i.e. last trading day)",
    )
    args = parser.parse_args()

    refresh(args.symbols, _as_of(args.date))


if __name__ == "__main__":
    main()