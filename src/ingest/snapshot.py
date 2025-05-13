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
    today = datetime.date.today().isoformat()
    resp = client.list_options_chain_agg(
        underlying_ticker="SPX", expiration_date=today
    )
    return pd.DataFrame([row.__dict__ for row in resp])

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