import pathlib, duckdb, datetime as dt, zoneinfo, pytest, glob

# location of today's parquet folder
TODAY = dt.datetime.now(zoneinfo.ZoneInfo("US/Eastern")).strftime("%Y-%m-%d")
PARQUET_GLOB = f"data/parquet/spx/date={TODAY}/*.parquet"

@pytest.mark.parametrize("file", glob.glob(PARQUET_GLOB))
def test_snapshot_file_basic(file):
    df = duckdb.query(f"SELECT * FROM read_parquet('{file}')").to_df()

    # 1. row count - 0DTE options have fewer strikes (~270 for both calls and puts)
    assert len(df) >= 100,   f"unexpectedly few strikes: {len(df)}"
    assert len(df) <= 500,   f"unexpectedly many strikes for 0DTE: {len(df)}"

    # 2. strikes should be reasonable for 0DTE (within ~15% of underlying)
    if len(df) > 0:
        under_px = df.under_px.iloc[0]
        min_strike = under_px * 0.85
        max_strike = under_px * 1.15
        assert df.strike.min() >= min_strike, f"Strike {df.strike.min()} too low for underlying {under_px}"
        assert df.strike.max() <= max_strike, f"Strike {df.strike.max()} too high for underlying {under_px}"

    # 3. no NULL greeks
    assert df.delta.notna().all()
    assert df.gamma.notna().all()
    assert df.theta.notna().all()
    assert df.vega.notna().all()