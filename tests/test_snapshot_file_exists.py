import pathlib, subprocess, os

def test_snapshot_creates_file(tmp_path, monkeypatch):
    """
    Test that snapshot creates files in the expected location.
    """
    from src.ingest import snapshot
    import pandas as pd

    # Mock path_for_now to return a test path
    test_path = tmp_path / "test.parquet"
    monkeypatch.setattr(snapshot, "path_for_now", lambda: test_path)

    # Mock fetch_chain to return test data
    test_df = pd.DataFrame({
        "strike": [420], 
        "bid": [1], 
        "ask": [1.2], 
        "type": ["C"],
        "expiry": ["2025-05-29"],
        "volume": [100],
        "open_interest": [50],
        "iv": [0.2],
        "delta": [0.5],
        "gamma": [0.01],
        "vega": [0.1],
        "theta": [-0.05],
        "under_px": [5920],
        "date": ["2025-05-29"]
    })
    monkeypatch.setattr(snapshot, "fetch_chain", lambda: test_df)
    
    # Run main which calls write_parquet_atomic
    snapshot.main()
    
    # Check file was created
    assert test_path.exists(), "Snapshot file should have been created"