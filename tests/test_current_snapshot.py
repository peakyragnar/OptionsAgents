"""Test current snapshot format and data quality for 0DTE options."""
import pathlib, duckdb, datetime as dt, zoneinfo, pytest, glob

# location of today's parquet folder
TODAY = dt.datetime.now(zoneinfo.ZoneInfo("US/Eastern")).strftime("%Y-%m-%d")
PARQUET_GLOB = f"data/parquet/spx/date={TODAY}/*.parquet"

@pytest.mark.parametrize("file", glob.glob(PARQUET_GLOB))
def test_snapshot_file_0dte(file):
    """Test 0DTE snapshot files have expected structure."""
    df = duckdb.query(f"SELECT * FROM read_parquet('{file}')").to_df()
    
    # 1. Row count appropriate for 0DTE (fewer strikes than weekly/monthly)
    assert len(df) >= 100, f"Too few strikes: {len(df)}"
    assert len(df) <= 500, f"Too many strikes for 0DTE: {len(df)}"
    
    # 2. Check required columns exist
    required_cols = {'type', 'strike', 'expiry', 'bid', 'ask', 'volume', 
                    'open_interest', 'iv', 'gamma', 'vega', 'theta', 'delta', 
                    'under_px', 'date'}
    assert set(df.columns) == required_cols, f"Column mismatch: {set(df.columns) ^ required_cols}"
    
    # 3. Strike range should be reasonable for 0DTE (within ~10% of underlying)
    under_px = df['under_px'].iloc[0]
    strike_range = df['strike'].max() - df['strike'].min()
    assert strike_range >= 0.1 * under_px, "Strike range too narrow"
    assert strike_range <= 0.3 * under_px, "Strike range too wide for 0DTE"
    
    # 4. Greeks should be non-null
    assert df['delta'].notna().all(), "Found null deltas"
    assert df['gamma'].notna().all(), "Found null gammas"
    assert df['theta'].notna().all(), "Found null thetas"
    assert df['vega'].notna().all(), "Found null vegas"
    
    # 5. Bid/ask should be mostly non-null (some far OTM might be null)
    assert df['bid'].notna().sum() / len(df) > 0.8, "Too many null bids"
    assert df['ask'].notna().sum() / len(df) > 0.8, "Too many null asks"