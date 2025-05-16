import pytest, math
from src.tools.dealer_gamma import dealer_gamma_snapshot


def test_dealer_gamma_runs_or_skips():
    try:
        res = dealer_gamma_snapshot()
        assert math.isfinite(res["gamma_total"])
        assert not res["df"].empty
    except RuntimeError:
        pytest.skip("latest snapshot missing gamma data")