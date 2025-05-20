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
    """Classify aggressor side, compute γ, update book.
    Ignore status/heartbeat frames that have no trade fields.
    """
    # For Polygon websocket format (different from original expected format)
    # Map Polygon fields to our internal format if needed
    if "ev" in msg and msg["ev"] == "OT":
        # This is a Polygon options trade message
        try:
            # Extract data from Polygon format
            sym = msg.get("sym")  # Option symbol
            price = msg.get("p")  # Price
            size = msg.get("s")   # Size
            timestamp = msg.get("t")  # Timestamp in nanoseconds
            
            # Log trade for debugging
            print(f"[engine] Processing trade: {sym} {size}@{price}")
            
            # Create standardized message
            trade_msg = {
                "sym": sym,
                "p": price,
                "s": size,
                "t": timestamp
            }
            msg = trade_msg
        except KeyError as e:
            print(f"[engine] Missing field in trade message: {e}")
            return
    
    # Verify we have all required fields
    if not {"sym", "p", "s", "t"}.issubset(msg):
        # Debug print to see what fields we received
        print(f"[engine] Incomplete trade message, fields: {msg.keys()}")
        return

    sym = msg["sym"]
    price = float(msg["p"])
    size = int(msg["s"])

    # Check if we have NBBO for this symbol
    bid, ask, _ = quotes.get(sym, (None, None, None))
    if bid is None:
        print(f"[engine] No NBBO for {sym}")
        return

    # Classify trade as BUY or SELL based on price relative to NBBO
    if price >= ask - eps:
        side = Side.BUY
        print(f"[engine] Classified as BUY: {price} >= {ask}-{eps}")
    elif price <= bid + eps:
        side = Side.SELL
        print(f"[engine] Classified as SELL: {price} <= {bid}+{eps}")
    else:
        print(f"[engine] Mid-trade ignored: {bid}+{eps} < {price} < {ask}-{eps}")
        return  # mid-trade ⇒ ignore

    try:
        # Parse OCC ticker
        occ = parse_occ(sym)
        
        # Calculate time to expiry properly
        trade_d = dt.datetime.utcfromtimestamp(msg["t"] / 1e9).date()
        tau_days = (occ.expiry - trade_d).days
        tau = max(tau_days / 365.0, 1/365.0)  # Ensure minimum time to expiry
        
        if tau <= 0:
            print(f"[engine] Option expired: {occ.expiry} <= {trade_d}")
            return

        # Get current SPX price (hard-coded for now, should fetch from real-time feed)
        spx_price = 5000  # Replace with actual SPX price lookup
        
        # Calculate mid price for IV calculation
        mid = (bid + ask) * 0.5
        
        # Get implied volatility
        sigma = _surface.get_sigma(sym, mid, S=spx_price, K=occ.strike, tau=tau)
        
        if math.isnan(sigma) or sigma <= 0:
            print(f"[engine] Invalid sigma for {sym}: {sigma}")
            # Use a reasonable fallback value instead of returning
            sigma = 0.2  # 20% volatility as fallback
        
        # Calculate gamma
        option_type = "C" if occ.is_call else "P"
        γ = bs_gamma(spx_price, occ.strike, sigma, tau, option_type)  # per-contract
        
        if math.isnan(γ) or γ <= 0:
            print(f"[engine] Invalid gamma for {sym}: {γ}")
            return
            
        # Update the dealer book
        print(f"[engine] Updating book: strike={occ.strike}, is_call={occ.is_call}, side={side}, size={size}, gamma={γ}")
        _book.update((occ.strike, occ.is_call), side, size, γ)
        
        # Log the total gamma after update
        print(f"[engine] Current total gamma: {_book.total_gamma()}")
        
    except Exception as e:
        print(f"[engine] Error processing trade: {type(e).__name__}: {e}")
        # Continue processing other trades

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