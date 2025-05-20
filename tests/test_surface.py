import math, time
from src.greeks.surface import VolSurface

class _FakeIV:
    """Deterministic solver so the test never depends on BS maths."""
    def __init__(self):
        self.calls = 0
    def __call__(self, mid, S, K, tau, r, q):
        self.calls += 1
        return 0.2 + 0.01 * self.calls

def test_surface_reuses_and_expires(monkeypatch):
    fake_iv = _FakeIV()
    # patch the solver used inside VolSurface
    monkeypatch.setattr("src.greeks.surface.iv_call", fake_iv)

    vs = VolSurface(eps=0.02, ttl=0.5)

    sym, mid, S, K, tau = "SYM", 10.0, 5000, 5000, 0.003

    s1 = vs.get_sigma(sym, mid, S, K, tau)
    assert math.isclose(s1, 0.21)

    # small move → no recalculation
    s2 = vs.get_sigma(sym, mid * 1.009, S, K, tau)
    assert s2 == s1
    assert fake_iv.calls == 1

    # big move → new calc
    s3 = vs.get_sigma(sym, mid * 1.05, S, K, tau)
    assert s3 != s1
    assert fake_iv.calls == 2

    # wait for TTL expiry
    time.sleep(0.6)
    s4 = vs.get_sigma(sym, mid * 1.051, S, K, tau)
    assert fake_iv.calls == 3