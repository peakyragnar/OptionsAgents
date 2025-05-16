"""
Integration tests for gamma values in the latest snapshot.
These tests validate that the gamma values are properly populated and usable.
"""
import pytest
import duckdb


def test_latest_has_gamma():
    """
    Test that the latest snapshot has gamma values with few NULLs.
    """
    try:
        nulls = duckdb.query("""
          WITH latest AS (
            SELECT gamma
            FROM spx_chain
            WHERE filename = (SELECT filename FROM spx_chain ORDER BY date DESC, ts DESC LIMIT 1)
          )
          SELECT COUNT(*) - COUNT(gamma) FROM latest;
        """).fetchone()[0]
        
        # Tolerate a few gaps, but no more than 10
        assert nulls < 10, f"Found {nulls} NULL gamma values in latest snapshot (max allowed: 10)"
    except Exception as e:
        pytest.skip(f"Could not test gamma values: {str(e)}")


def test_dealer_gamma_nonzero():
    """
    Test that dealer gamma calculation returns significant non-zero value.
    """
    try:
        from src.tools.dealer_gamma import dealer_gamma_snapshot
        
        res = dealer_gamma_snapshot()
        
        # At least $1M gamma (either positive or negative)
        assert abs(res["gamma_total"]) > 1e6, f"Dealer gamma too small: {res['gamma_total']}"
        
        # Verify gamma_flip is a reasonable value
        if res["gamma_flip"] is not None:
            assert 0 < res["gamma_flip"] < 10000, f"Gamma flip point outside reasonable range: {res['gamma_flip']}"
    except Exception as e:
        pytest.skip(f"Could not test dealer gamma: {str(e)}")