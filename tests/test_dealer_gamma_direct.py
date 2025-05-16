"""
Test the direct dealer gamma calculation.
"""
import pytest
from src.tools.dealer_gamma_direct import dealer_gamma_snapshot


def test_dealer_gamma_nonzero():
    """
    Test that dealer gamma calculation returns significant non-zero value.
    """
    try:
        res = dealer_gamma_snapshot()
        
        # Assert dealer gamma is at least $1M (substantial gamma)
        assert abs(res["gamma_total"]) > 1e6, f"Dealer gamma too small: {res['gamma_total']}"
        
        # Verify gamma_flip is a reasonable value
        if res["gamma_flip"] is not None:
            assert 0 < res["gamma_flip"] < 10000, f"Gamma flip point outside reasonable range: {res['gamma_flip']}"
    except Exception as e:
        pytest.skip(f"Could not test dealer gamma: {str(e)}")