import pathlib, duckdb, datetime as dt, zoneinfo, pytest, glob

# location of today's parquet folder
TODAY = dt.datetime.now(zoneinfo.ZoneInfo("US/Eastern")).strftime("%Y-%m-%d")
PARQUET_GLOB = f"data/parquet/spx/date={TODAY}/*.parquet"

@pytest.mark.parametrize("file", glob.glob(PARQUET_GLOB))
def test_snapshot_file_basic(file):
    df = duckdb.query(f"SELECT * FROM read_parquet('{file}')").to_df()

    # 1. row count
    assert len(df) >= 450,   "unexpectedly few strikes"

    # 2. strikes cover a wide range
    assert df.strike.min() < 3000
    assert df.strike.max() > 7000

    # 3. no NULL greeks
    assert df.delta.notna().all()
    assert df.gamma.notna().all()