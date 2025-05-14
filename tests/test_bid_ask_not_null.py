import duckdb, pytest, glob

def test_bid_ask_not_null():
    glob_path = "data/parquet/spx/date=*/*.parquet"
    if not glob.glob(glob_path):
        pytest.skip("no snapshot file available")
    bid_nulls, ask_nulls = duckdb.query(f"""
        SELECT COUNT(*)-COUNT(bid), COUNT(*)-COUNT(ask)
        FROM parquet_scan('{glob_path}')
    """).fetchone()
    assert bid_nulls == 0 and ask_nulls == 0, f"Null bids={bid_nulls} asks={ask_nulls}"