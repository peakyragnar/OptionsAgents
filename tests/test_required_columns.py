import duckdb, pytest, glob

EXPECTED = {
    "type","strike","expiry","bid","ask","volume",
    "open_interest","iv","delta","gamma","vega","theta","under_px","date"
}

def test_required_columns_present():
    files = glob.glob("data/parquet/spx/date=*/*.parquet")
    if not files:
        pytest.skip("no snapshot file available")
    file = files[-1]     # latest snapshot
    
    # Use read_parquet to get actual columns instead of parquet_schema
    # which may not show all columns correctly
    df = duckdb.query(f"SELECT * FROM read_parquet('{file}') LIMIT 0").to_df()
    cols = set(df.columns)
    
    assert cols == EXPECTED, f"columns mismatch: {cols.symmetric_difference(EXPECTED)}"