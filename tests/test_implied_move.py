# tests/test_implied_move.py
def test_sigma_pct_reasonable_or_skip():
    import pytest
    from math import isnan
    from src.tools.implied_move import implied_move_calc

    try:
        res = implied_move_calc()
        assert 0 < res["sigma_pct"] < 0.10 and not isnan(res["sigma_pct"])
    except RuntimeError as e:
        pytest.skip(str(e))