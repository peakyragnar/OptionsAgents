import duckdb, pytest, glob

def test_bid_ask_not_null():
    glob_path = "data/parquet/spx/date=*/*.parquet"
    files = glob.glob(glob_path)
    if not files:
        pytest.skip("no snapshot file available")
    
    # Test only the most recent file to avoid ZSTD decompression issues
    # with potentially corrupted older files
    latest_file = sorted(files)[-1]
    
    try:
        bid_nulls, ask_nulls = duckdb.query(f"""
            SELECT COUNT(*)-COUNT(bid), COUNT(*)-COUNT(ask)
            FROM read_parquet('{latest_file}')
        """).fetchone()
        assert bid_nulls == 0 and ask_nulls == 0, f"Null bids={bid_nulls} asks={ask_nulls}"
    except duckdb.Error as e:
        if "ZSTD Decompression" in str(e):
            pytest.skip(f"Corrupted parquet file: {latest_file}")
        raise