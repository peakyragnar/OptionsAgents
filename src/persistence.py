"""
Persistence utilities for dealer gamma snapshots.
Stores snapshots in DuckDB for querying and visualization.
"""

import os, duckdb, pathlib, threading, atexit, datetime as dt

_DB = pathlib.Path(os.getenv("OA_GAMMA_DB", "data/intraday.db"))
_CONN = None  # We'll initialize the connection on first use
_LOCK = threading.Lock()

def _get_connection():
    """Get or create a connection to the database"""
    global _CONN
    if _CONN is None:
        _DB.parent.mkdir(parents=True, exist_ok=True)
        _CONN = duckdb.connect(str(_DB), read_only=False, config={'access_mode':'AUTOMATIC'})
        _CONN.execute("""
        CREATE TABLE IF NOT EXISTS intraday_gamma (
            ts DOUBLE,
            dealer_gamma DOUBLE
        )
        """)
        # Register function to close connection at exit
        atexit.register(lambda: _CONN.close() if _CONN else None)
    return _CONN

def append_gamma(ts: float, gamma: float) -> None:
    """
    Thread-safe append of a gamma snapshot to the database.
    
    Args:
        ts: Unix timestamp (seconds since epoch)
        gamma: Total dealer gamma value
    """
    with _LOCK:
        conn = _get_connection()
        conn.execute(
            "INSERT INTO intraday_gamma VALUES (?, ?)",
            (ts, gamma),
        )

def get_latest_gamma():
    """Get the latest gamma snapshot"""
    with _LOCK:
        conn = _get_connection()
        result = conn.execute("""
        SELECT ts, dealer_gamma
        FROM intraday_gamma
        ORDER BY ts DESC
        LIMIT 1
        """).fetchone()
        
    if result:
        ts = result[0]
        return {
            "ts": ts, 
            "gamma": result[1], 
            "time": dt.datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S')
        }
    return None

def get_gamma_history(limit=100):
    """Get historical gamma values"""
    with _LOCK:
        conn = _get_connection()
        df = conn.execute(f"""
        SELECT ts, dealer_gamma
        FROM intraday_gamma
        ORDER BY ts DESC
        LIMIT {limit}
        """).fetchdf()
    
    if not df.empty:
        # Convert ts to readable time
        df['time'] = df['ts'].apply(lambda x: dt.datetime.fromtimestamp(x).strftime('%Y-%m-%d %H:%M:%S'))
    
    return dfimport os, duckdb; p = os.getenv("OA_GAMMA_DB"); \
      duckdb.connect(p).close() if p else None
