"""
Pull one snapshot of today's SPX 0-DTE option chain
and store it here:

data/parquet/spx/date=YYYY-MM-DD/HH_MM_SS.parquet
"""

import os, pathlib, datetime, dotenv
import pandas as pd
from polygon import RESTClient

# 1. API key
dotenv.load_dotenv()
API_KEY = os.getenv("POLYGON_KEY")
if not API_KEY:
    raise RuntimeError("POLYGON_KEY missing in .env")

client = RESTClient(API_KEY)

# 2. fetch chain (today’s expiry only)
def fetch_chain():
    """
    Return a DataFrame of *today's* SPX 0-DTE calls and puts
    with basic market fields.
    """
    today = datetime.date.today().isoformat()

    # Get snapshot of SPX options chain
    options_chain = client.list_snapshot_options_chain(
        "SPX",
        params={"expiration_date": today}
    )
    rows = []

    # Process options from the chain
    for opt in options_chain:
        # Determine if call or put
        side = "C" if opt.details.contract_type == "call" else "P"
        rows.append({
            "type":   side,
            "strike": opt.details.strike_price,
            "expiry": opt.details.expiration_date,
            "bid":    getattr(opt.last_quote, "bid", None),    # intraday quote
            "ask":    getattr(opt.last_quote, "ask", None),    # intraday quote
            "volume": getattr(opt.day, "volume", 0),
            "open_interest": getattr(opt.details, "open_interest", 0),
            "iv":     getattr(opt.greeks, "implied_volatility", None) if hasattr(opt, "greeks") else None,
            "delta":  getattr(opt.greeks, "delta", None) if hasattr(opt, "greeks") else None,
            "gamma":  getattr(opt.greeks, "gamma", None) if hasattr(opt, "greeks") else None,
            "under_px": getattr(opt.underlying, "price", None) if hasattr(opt, "underlying") else None
        })

    return pd.DataFrame(rows)

# 3. write parquet in partitioned path
def write_parquet(df: pd.DataFrame):
    ts   = datetime.datetime.now()
    path = pathlib.Path("data/parquet/spx") \
           / f"date={ts.date()}"            \
           / f"{ts:%H_%M_%S}.parquet"
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, compression="zstd")
    return path

if __name__ == "__main__":
    df = fetch_chain()
    if df.empty:
        raise SystemExit("Polygon returned zero rows")
    p = write_parquet(df)
    print(f"Wrote {len(df)} rows → {p}")