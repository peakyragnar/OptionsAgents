"""
Pull one snapshot of today's SPX 0-DTE option chain
and store it here:

data/parquet/spx/date=YYYY-MM-DD/HH_MM_SS.parquet
"""

import datetime, os, pathlib, dotenv, pandas as pd
from polygon import RESTClient

dotenv.load_dotenv()
client = RESTClient(os.getenv("POLYGON_KEY"))

def fetch_chain() -> pd.DataFrame:
    today = datetime.date.today().isoformat()

    # 1. OPTION-CHAIN SNAPSHOT  (v3)
    # ------------------------------------------------------------------
    # Get options with limit to avoid timeout, focus on today's expiry
    try:
        # Try with params to filter by expiration date
        options_iter = client.list_snapshot_options_chain(
            "SPX",
            params={"expiration_date": today}
        )
        
        # Convert limited options to list
        print("Fetching options chain (limited to 500 contracts)...")
        all_options = []
        for i, opt in enumerate(options_iter):
            all_options.append(opt)
            if i >= 499:  # Extra safety to ensure we don't process too many
                break
                
        print(f"Retrieved {len(all_options)} options")
        
        # Separate calls and puts
        calls = [opt for opt in all_options if opt.details.contract_type == "call"]
        puts = [opt for opt in all_options if opt.details.contract_type == "put"]
        print(f"Found {len(calls)} calls and {len(puts)} puts")
    except Exception as e:
        raise RuntimeError(f"Failed to retrieve options chain: {e}")
    # ------------------------------------------------------------------

# 2. INDEX PRICE - try multiple API approaches ───────────────────────
    try:
        # Method 1: Try previous close (reliable data point)
        prev_close = client.get_previous_close("I:SPX")
        under_px = prev_close.close
        print(f"Using SPX previous close: {under_px}")
    except Exception as e1:
        try:
            # Method 2: Try daily OHLC
            daily = client.get_daily_open_close("I:SPX", datetime.date.today().isoformat())
            under_px = daily.close
            print(f"Using SPX daily close: {under_px}")
        except Exception as e2:
            try:
                # Method 3: Try aggregates for today
                from_date = datetime.date.today().isoformat()
                to_date = from_date
                aggs = client.get_aggs("I:SPX", 1, "day", from_date, to_date, limit=10)
                if aggs:
                    under_px = aggs[0].close
                    print(f"Using SPX aggregate close: {under_px}")
                else:
                    raise RuntimeError("No aggregate data available for I:SPX")
            except Exception as e3:
                # Fail with detailed error information
                raise RuntimeError(
                    f"Unable to get SPX price from any endpoint. "
                    f"Previous close error: {e1}, "
                    f"Daily OHLC error: {e2}, "
                    f"Aggregates error: {e3}"
                )
    # ──────────────────────────────────────────────────────────────

    rows = []
    for side, opt_list in (("C", calls), ("P", puts)):
        for opt in opt_list:
            if opt.details.expiration_date != today:
                continue
            rows.append({
                "type":   side,
                "strike": opt.details.strike_price,
                "expiry": opt.details.expiration_date,
                "bid":    getattr(opt.last_quote, "bid", None),       # Correct field name
                "ask":    getattr(opt.last_quote, "ask", None),       # Correct field name
                "volume": getattr(opt.day, "volume", 0),
                "open_interest": getattr(opt.details, "open_interest", 0),
                "iv":     getattr(opt.greeks, "iv", None),
                "delta":  getattr(opt.greeks, "delta", None),
                "gamma":  getattr(opt.greeks, "gamma", None),
                "under_px": under_px
            })

    return pd.DataFrame(rows)

# ---- file-writer unchanged ----
def write_parquet(df: pd.DataFrame):
    ts   = datetime.datetime.now()
    path = pathlib.Path("data/parquet/spx") / f"date={ts.date()}" / f"{ts:%H_%M_%S}.parquet"
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, compression="zstd")
    return path

if __name__ == "__main__":
    df = fetch_chain()
    if df.empty:
        raise SystemExit("Polygon returned zero rows")
    p = write_parquet(df)
    print(f"Wrote {len(df)} rows → {p}")