"""
Persistence utilities for dealer gamma snapshots.
Stores snapshots in DuckDB for querying and visualization.
"""

import os, duckdb, pathlib, threading

_DB = pathlib.Path(os.getenv("OA_GAMMA_DB", "data/intraday.db"))
_CONN = duckdb.connect(_DB, read_only=False, config={'access_mode':'AUTOMATIC'})
_CONN.execute("""
CREATE TABLE IF NOT EXISTS intraday_gamma (
    ts DOUBLE,
    dealer_gamma DOUBLE
)
""")
_LOCK = threading.Lock()

def append_gamma(ts: float, gamma: float) -> None:
    """
    Thread-safe append of a gamma snapshot to the database.
    
    Args:
        ts: Unix timestamp (seconds since epoch)
        gamma: Total dealer gamma value
    """
    with _LOCK:
        _CONN.execute(
            "INSERT INTO intraday_gamma VALUES (?, ?)",
            (ts, gamma),
        )