from src.tools.dealer_gamma_live import dealer_gamma_live
import pytest, numpy as np

def test_live_snapshot_available():
    try:
        g = dealer_gamma_live()
    except RuntimeError:
        pytest.skip("no intraday snapshot yet")
    assert isinstance(g["gamma_total"], np.floating)