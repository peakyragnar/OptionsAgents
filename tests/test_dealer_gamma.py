import pytest, math
from src.tools.dealer_gamma import dealer_gamma_snapshot as dg_duckdb
from src.tools.dealer_gamma_direct import dealer_gamma_snapshot as dg_direct


def test_dealer_gamma_runs_or_skips():
    """Test that the DuckDB implementation runs or skips if data is missing."""
    try:
        res = dg_duckdb()
        assert math.isfinite(res["gamma_total"])
        assert not res["df"].empty
    except RuntimeError:
        pytest.skip("latest snapshot missing gamma data")


def test_dealer_gamma_implementations_match():
    """Test that both dealer gamma implementations produce similar results."""
    try:
        result_duckdb = dg_duckdb()
        result_direct = dg_direct()
        
        # Print results for comparison
        print(f"\nDuckDB implementation:")
        print(f"Total dealer gamma: ${result_duckdb['gamma_total']:,.2f}")
        print(f"Gamma flip level: {result_duckdb['gamma_flip']:.2f}")
        
        print(f"\nDirect implementation:")
        print(f"Total dealer gamma: ${result_direct['gamma_total']:,.2f}")
        print(f"Gamma flip level: {result_direct['gamma_flip']:.2f}")
        
        # Test that the results are similar (within 10%)
        duckdb_gamma = result_duckdb['gamma_total']
        direct_gamma = result_direct['gamma_total']
        
        # Check if either value is zero to avoid division by zero
        if abs(duckdb_gamma) < 1e-6 or abs(direct_gamma) < 1e-6:
            assert abs(duckdb_gamma - direct_gamma) < 1e6, "Gamma values differ significantly but one is near zero"
        else:
            ratio = abs(duckdb_gamma / direct_gamma)
            assert 0.9 <= ratio <= 1.1, f"Gamma values differ by more than 10%: ratio={ratio}"
            
        # Check gamma flip point is similar
        duckdb_flip = result_duckdb['gamma_flip']
        direct_flip = result_direct['gamma_flip']
        
        if duckdb_flip is not None and direct_flip is not None:
            flip_diff = abs(duckdb_flip - direct_flip)
            assert flip_diff <= 50, f"Gamma flip points differ by more than 50 points: diff={flip_diff}"
            
    except RuntimeError as e:
        pytest.skip(f"Test skipped: {str(e)}")
    except Exception as e:
        pytest.fail(f"Exception occurred: {str(e)}")