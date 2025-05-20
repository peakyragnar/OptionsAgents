import asyncio, math, time, types, pytest
from src.dealer.engine import run as engine_run, _book
from src.stream.trade_feed import TRADE_Q
from src.stream.quote_cache import quotes
from src.utils.greeks import gamma, bs_greeks, implied_vol_call, implied_vol_put, implied_vol

def test_gamma_wrapper():
    """Test that the gamma wrapper correctly extracts gamma from bs_greeks."""
    assert math.isclose(gamma(5000, 5000, 0.2, 0.002),
                        bs_greeks(5000, 5000, 0.2, 0.002, "C")[0])
    
def test_implied_vol_wrappers():
    """Test that the implied vol wrappers correctly call the base function."""
    # Create a mock for the base function
    original_implied_vol = implied_vol
    
    try:
        # Track calls to implied_vol
        calls = []
        def mock_implied_vol(price, s, k, tau, cp):
            calls.append((price, s, k, tau, cp))
            return 0.2  # Return a dummy value
            
        # Install the mock
        pytest.MonkeyPatch().setattr("src.utils.greeks.implied_vol", mock_implied_vol)
        
        # Call the wrappers
        implied_vol_call(1.0, 100, 100, 0.1)
        implied_vol_put(2.0, 200, 200, 0.2)
        
        # Verify the calls
        assert calls[0] == (1.0, 100, 100, 0.1, "C")
        assert calls[1] == (2.0, 200, 200, 0.2, "P")
    finally:
        # Restore the original function
        pytest.MonkeyPatch().setattr("src.utils.greeks.implied_vol", original_implied_vol)

@pytest.mark.asyncio
async def test_engine_updates(monkeypatch):
    # --- stub out greeks.gamma and VolSurface.get_sigma for speed ---
    monkeypatch.setattr("src.dealer.engine.bs_greeks", lambda *a, **k: (0.01, 0, 0))
    monkeypatch.setattr("src.dealer.engine._surface.get_sigma", lambda *a, **k: 0.20)

    # Clear book to ensure clean test state
    _book._long.clear()
    _book._short.clear()
    _book._gamma.clear()

    # Clear queue to ensure clean test state
    while not TRADE_Q.empty():
        try:
            TRADE_Q.get_nowait()
        except asyncio.QueueEmpty:
            break

    # preload NBBO for symbol
    sym = "O:SPXW250519P05000000"
    quotes[sym] = (1.0, 1.1, 0)           # bid, ask, ts

    # prepare snapshot sink
    snapshots = []
    def snap_cb(ts, g): snapshots.append(g)

    # push one fake BUY trade
    TRADE_Q.put_nowait({"sym": sym, "p": 1.1, "s": 2, "t": 0})

    task = asyncio.create_task(engine_run(snap_cb, eps=0.05, snapshot_interval=0.1))
    await asyncio.sleep(0.2)
    task.cancel()
    try:
        await task  # Handle cancellation
    except asyncio.CancelledError:
        pass

    # one trade, BUY => dealer short γ (-)
    assert math.isclose(_book.total_gamma(), -0.01 * 2, rel_tol=1e-9)
    # snapshot callback fired at least once
    assert snapshots and math.isclose(snapshots[-1], _book.total_gamma(), rel_tol=1e-9)