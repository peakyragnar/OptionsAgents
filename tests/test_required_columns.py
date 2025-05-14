import duckdb, pytest, glob

EXPECTED = {
    "type","strike","expiry","bid","ask","volume",
    "open_interest","iv","delta","gamma","under_px"
}

def test_required_columns_present():
    files = glob.glob("data/parquet/spx/date=*/*.parquet")
    if not files:
        pytest.skip("no snapshot file available")
    file = files[-1]     # latest snapshot
    cols = set(r[0] for r in duckdb.query(
        f"SELECT name FROM parquet_schema('{file}') "
        "WHERE name <> 'schema'"          # filter out synthetic schema row
    ).fetchall())
    assert cols == EXPECTED, f"columns mismatch: {cols.symmetric_difference(EXPECTED)}"