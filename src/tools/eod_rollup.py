# src/tools/eod_rollup.py
import sys
import datetime as dt
import duckdb
import pathlib

def rollup(date: dt.date, symbol: str = "spx") -> None:
    snap = f"data/parquet/{symbol}/date={date}/*.parquet"
    con  = duckdb.connect("data/intraday.db")
    src  = f"(SELECT * FROM parquet_scan('{snap}'))"

    # ❶ fetch average underlying price for the day
    spot = con.sql(f"SELECT AVG(under_px) FROM {src}").fetchone()[0]

    # ❷ write/update daily tables
    con.sql(f"""
      CREATE OR REPLACE TABLE {symbol}_daily_straddle AS
      SELECT '{date}'::DATE        AS date,
             {spot}::DOUBLE        AS under_px,
             AVG(bid + ask)        AS atm_straddle      -- only Δ≈0.5 rows
      FROM {src}
      WHERE ABS(ABS(delta) - 0.5) < 0.025;   -- keep |Δ| ∈ [0.475, 0.525]
    """)

    con.sql(f"""
      CREATE OR REPLACE TABLE {symbol}_net_gamma AS
      SELECT strike,
             SUM(open_interest * gamma) AS net_gamma
      FROM {src}
      GROUP BY strike;
    """)

    con.sql(f"""
      CREATE OR REPLACE TABLE {symbol}_volume_agg AS
      SELECT strike,
             SUM(volume) AS vol
      FROM {src}
      GROUP BY strike;
    """)
    con.close()

if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit("Usage: python -m src.tools.eod_rollup YYYY-MM-DD")
    rollup(dt.date.fromisoformat(sys.argv[1]))