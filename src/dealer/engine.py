"""
dealer.engine
=============
Consumes `stream.trade_feed.TRADE_Q`, looks up NBBO in
`stream.quote_cache.quotes`, converts trades to dealer-gamma updates, and
emits snapshots.

Public coroutine
----------------
run(snapshot_cb: Callable[[float, float], None], *,
    eps: float = 0.05,   # aggressor threshold $
    snapshot_interval: float = 1.0) -> None
"""
from __future__ import annotations
import asyncio, time, math, datetime as dt
from typing import Callable

from src.stream.trade_feed import TRADE_Q
from src.stream.quote_cache import quotes            # live NBBO cache
from src.greeks.surface import VolSurface
from src.utils.occ import parse as parse_occ
from src.dealer.strike_book import StrikeBook, Side
from src.utils.greeks import gamma as bs_gamma     # scalar γ

_surface = VolSurface()          # single cache instance
_book    = StrikeBook()          # module-level so agents can inspect

async def _process_trade(msg: dict, *, eps: float) -> None:
    """Classify aggressor side, compute γ, update book."""
    sym  = msg["sym"]
    price= msg["p"]
    size = msg["s"]

    bid, ask, _ = quotes.get(sym, (None, None, None))
    if bid is None:                    # no NBBO yet
        return

    if price >= ask - eps:
        side = Side.BUY
    elif price <= bid + eps:
        side = Side.SELL
    else:
        return                        # mid-trade ⇒ ignore

    # parse OCC ticker
    occ = parse_occ(sym)
    
    # Calculate time to expiry properly
    trade_d  = dt.datetime.utcfromtimestamp(msg["t"] / 1e9).date()
    tau_days = (occ.expiry - trade_d).days
    tau      = tau_days / 365.0
    
    if tau <= 0:
        return

    mid = (bid + ask) * 0.5
    sigma = _surface.get_sigma(sym, mid, S=5000, K=occ.strike, tau=tau)    # S hard-coded; replace later
    if math.isnan(sigma):
        return
    γ = bs_gamma(5000, occ.strike, sigma, tau, "C" if occ.is_call else "P")   # per-contract
    _book.update((occ.strike, occ.is_call), side, size, γ)

async def run(snapshot_cb: Callable[[float, float], None], *, 
              eps: float = 0.05, snapshot_interval: float = 1.0) -> None:
    """
    snapshot_cb(ts: float, total_gamma: float)  called every `snapshot_interval` seconds.
    """
    last = time.time()
    while True:
        try:
            msg = await asyncio.wait_for(TRADE_Q.get(), timeout=0.2)
            await _process_trade(msg, eps=eps)
        except asyncio.TimeoutError:
            pass

        now = time.time()
        if now - last >= snapshot_interval:
            snapshot_cb(now, _book.total_gamma())
            last = now