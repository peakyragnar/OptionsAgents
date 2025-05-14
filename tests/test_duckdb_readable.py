import duckdb, pytest, pathlib, glob

SNAP_GLOB = "data/parquet/spx/date=*/*.parquet"

def test_duckdb_reads_live_file():
    files = glob.glob(SNAP_GLOB)
    if not files:
        pytest.skip("no live snapshot file found in data/parquet")
    rows = duckdb.query(f"SELECT COUNT(*) FROM parquet_scan('{SNAP_GLOB}')").fetchone()[0]
    assert rows > 0, "snapshot Parquet is unreadable or empty"