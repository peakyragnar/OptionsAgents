import duckdb
import math
from pathlib import Path

DB = Path("market.duckdb")

def _latest_snapshot_null_counts():
    sql = """
    WITH latest AS (
      SELECT gamma, open_interest
      FROM   spx_chain
      WHERE  filename = (
            SELECT filename
            FROM   spx_chain
            ORDER  BY date DESC, ts DESC
            LIMIT 1)
    )
    SELECT
        COUNT(*)                                   AS rows,
        SUM(gamma IS NULL OR isnan(gamma))         AS null_gamma,
        SUM(open_interest IS NULL OR open_interest = 0) AS bad_oi
    FROM latest;
    """
    rows, null_gamma, bad_oi = duckdb.connect(DB, read_only=True).execute(sql).fetchone()
    return rows, null_gamma, bad_oi

def test_snapshot_has_no_null_gamma():
    rows, null_gamma, _ = _latest_snapshot_null_counts()
    assert null_gamma == 0, f"{null_gamma} null-gamma rows in latest snapshot ({rows} rows total)"

def test_snapshot_has_open_interest():
    rows, _, bad_oi = _latest_snapshot_null_counts()
    assert bad_oi == 0, f"{bad_oi} rows have zero/NULL open_interest in latest snapshot ({rows} rows total)"