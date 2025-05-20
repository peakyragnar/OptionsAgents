import asyncio, math, time, types, pytest
from src.dealer.engine import run as engine_run, _book
from src.stream.trade_feed import TRADE_Q
from src.stream.quote_cache import quotes

@pytest.mark.asyncio
async def test_engine_updates(monkeypatch):
    """
    Test that the engine processes trades correctly and updates the strike book.
    Patch the heavy math functions for speed and determinism.
    """
    # --- stub out greeks.gamma and VolSurface.get_sigma for speed ---
    monkeypatch.setattr("src.dealer.engine.bs_gamma", lambda *a, **k: 0.01)
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

    task = asyncio.create_task(
        engine_run(snap_cb, eps=0.05, snapshot_interval=0.1)
    )
    await asyncio.sleep(0.3)          # allow snapshot to fire
    task.cancel()
    try:
        await task  # Handle cancellation
    except asyncio.CancelledError:
        pass

    # one trade, BUY => dealer short γ (-)
    assert math.isclose(_book.total_gamma(), -0.01 * 2, rel_tol=1e-9)
    # snapshot callback fired at least once
    assert snapshots and math.isclose(snapshots[-1], _book.total_gamma(), rel_tol=1e-9)