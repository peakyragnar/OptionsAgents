# src/snapshots/oi_builder.py
"""
Build an intraday open-interest snapshot per option symbol.

Usage:
    PYTHONPATH=. python src/snapshots/oi_builder.py --date 2025-05-21
"""
import argparse, pathlib, duckdb, pyarrow.parquet as pq

def classify_side(price, bid, ask):
    """
    Very simple heuristic:
        • Buyer pays the ask  -> opening   (+1)
        • Seller hits the bid -> closing   (−1)
        • Otherwise           -> ignore     0
    Multiplying by trade size gives net contracts.
    """
    if price >= ask: return +1
    if price <= bid: return -1
    return 0

def build_snapshot(glob_pattern, out_path):
    con = duckdb.connect()
    
    # ── build snapshot ───────────────────────────────────────────────────
    con.execute(f"""
        COPY (
            SELECT  symbol                                    AS sym ,
                    SUM(
                        CASE
                            WHEN lower(side) IN ('b','buy')  THEN  size
                            WHEN lower(side) IN ('s','sell') THEN -size
                            ELSE 0
                        END
                    )                                         AS net_open_contracts
            FROM    read_parquet('{glob_pattern}')
            GROUP   BY 1
        )
        TO '{out_path}' (FORMAT PARQUET);
    """)
    print(f"✓ snapshot saved → {out_path}")

if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--date", required=True, help="YYYY-MM-DD")
    args = p.parse_args()

    day = args.date
    glob_pattern = f"data/{day}/trades.parquet/*.parquet"
    out_path      = pathlib.Path(f"data/{day}/oi_snapshot.parquet")
    build_snapshot(glob_pattern, out_path)