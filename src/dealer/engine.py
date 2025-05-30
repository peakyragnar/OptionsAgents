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
import logging
from typing import Callable

from src.utils.logging_config import setup_application_logging, setup_component_logger
from src.stream.shared_queue import get_trade_queue
from src.stream.quote_cache import quotes            # live NBBO cache
from src.greeks.surface import VolSurface

# Initialize logging
setup_application_logging()
logger = setup_component_logger(__name__)
from src.utils.occ import parse as parse_occ
from src.dealer.strike_book import StrikeBook, Side
from src.utils.greeks import gamma as bs_gamma     # scalar γ

_surface = VolSurface()          # single cache instance
_book    = StrikeBook()          # module-level so agents can inspect

async def _process_trade(msg: dict, *, eps: float) -> None:
    """Classify aggressor side, compute γ, update book.
    Ignore status/heartbeat frames that have no trade fields.
    """
    # Debug: log what we received
    print(f"[engine] _process_trade received: {msg}", flush=True)
    
    # Handle status messages - skip them entirely
    if "status" in msg:
        print(f"[engine] Skipping status message: {msg.get('status')} - {msg.get('message', '')}")
        return
        
    # For Polygon websocket format (different from original expected format)
    # Map Polygon fields to our internal format if needed
    if "ev" in msg:
        # Check if this is a valid trade message
        if msg.get("ev") == "OT" and all(k in msg for k in ["sym", "p", "s", "t"]):
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
        else:
            # This is a different message type - log and skip
            print(f"[engine] Skipping message with event type '{msg.get('ev')}', fields: {msg.keys()}")
            return
    
    # Handle different field naming conventions
    if "price" in msg and "size" in msg:
        # Map field names from trade feed format to expected format
        msg["p"] = msg["price"]
        msg["s"] = msg["size"]
        # Convert timestamp to nanoseconds if needed
        ts = msg.get("timestamp", msg.get("ts", 0))
        if isinstance(ts, float) and ts < 1e10:  # Timestamp in seconds
            msg["t"] = int(ts * 1e9)  # Convert to nanoseconds
        else:
            msg["t"] = ts
        print(f"[engine] Mapped trade fields: {msg['sym']} {msg['s']}@{msg['p']}")
    
    # Verify we have all required fields
    if not {"sym", "p", "s", "t"}.issubset(msg):
        # Debug print to see what fields we received
        print(f"[engine] Incomplete trade message, fields: {msg.keys()}")
        print(f"[engine] Message content: {msg}")
        return

    sym = msg["sym"]
    price = float(msg["p"])
    size = int(msg["s"])

    # Check if we have NBBO for this symbol
    quote = quotes.get(sym, {})
    if isinstance(quote, dict):
        bid = quote.get("bid")
        ask = quote.get("ask")
    else:
        # Legacy tuple format
        bid, ask, _ = quote if quote else (None, None, None)
    
    if bid is None or ask is None:
        print(f"[engine] No NBBO for {sym}")
        return
    
    # Ensure bid/ask are floats
    bid = float(bid)
    ask = float(ask)

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
        # Handle timestamp in different formats
        timestamp = msg.get("t", msg.get("timestamp", 0))
        if timestamp > 1e10:  # Nanoseconds
            trade_d = dt.datetime.utcfromtimestamp(timestamp / 1e9).date()
        else:  # Seconds
            trade_d = dt.datetime.utcfromtimestamp(timestamp).date()
        tau_days = (occ.expiry - trade_d).days
        tau = max(tau_days / 365.0, 1/365.0)  # Ensure minimum time to expiry
        
        if tau <= 0:
            print(f"[engine] Option expired: {occ.expiry} <= {trade_d}")
            return

        # Get current SPX price from quote cache
        spx_quote = quotes.get("I:SPX", {})
        if isinstance(spx_quote, dict):
            spx_bid = spx_quote.get("bid")
            spx_ask = spx_quote.get("ask")
            if spx_bid and spx_ask:
                spx_price = (float(spx_bid) + float(spx_ask)) / 2
            else:
                spx_price = 5875  # Fallback
                print(f"[engine] Warning: No SPX quote available, using fallback price {spx_price}")
        else:
            # Legacy tuple format
            if spx_quote and spx_quote[0] is not None and spx_quote[1] is not None:
                spx_price = (float(spx_quote[0]) + float(spx_quote[1])) / 2
            else:
                spx_price = 5875
                print(f"[engine] Warning: No SPX quote available, using fallback price {spx_price}")
        
        # Calculate mid price for IV calculation and Greeks
        mid = (bid + ask) * 0.5
        
        # Get implied volatility using mid price (not trade price)
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
    print(f"[engine] 🚀 DEALER ENGINE STARTED! eps={eps}, snapshot_interval={snapshot_interval}", flush=True)
    print(f"[engine] Callback function: {snapshot_cb.__name__}", flush=True)
    trade_queue = get_trade_queue()
    print(f"[engine] Got trade queue: {id(trade_queue)} in event loop: {id(asyncio.get_event_loop())}", flush=True)
    print(f"[engine] Initial queue size: {trade_queue.qsize()}", flush=True)
    logger.info(f"Dealer engine started with queue size: {trade_queue.qsize()}")
    last = time.time()
    trade_count = 0
    
    print(f"[engine] Entering main loop...", flush=True)
    loop_count = 0
    while True:
        loop_count += 1
        if loop_count <= 5 or loop_count % 100 == 0:
            print(f"[engine] Loop iteration {loop_count}, queue size: {trade_queue.qsize()}", flush=True)
        
        try:
            # Debug: check queue periodically
            if trade_count % 100 == 0:
                print(f"[engine] Queue check: {trade_queue.qsize()} items, processed {trade_count} trades", flush=True)
            msg = await asyncio.wait_for(trade_queue.get(), timeout=0.2)
            trade_count += 1
            print(f"[engine] Got trade #{trade_count} from queue: {msg}", flush=True)
            if trade_count % 10 == 0:
                print(f"[engine] Processed {trade_count} trades, current gamma: {_book.total_gamma()}", flush=True)
            await _process_trade(msg, eps=eps)
        except asyncio.TimeoutError:
            if loop_count % 50 == 0:
                print(f"[engine] Timeout waiting for trades, continuing...", flush=True)

        now = time.time()
        if now - last >= snapshot_interval:
            gamma = _book.total_gamma()
            print(f"[engine] Snapshot: gamma={gamma}, trades={trade_count}", flush=True)
            try:
                snapshot_cb(now, gamma)
                print(f"[engine] Snapshot callback completed", flush=True)
            except Exception as e:
                print(f"[engine] ERROR in snapshot callback: {type(e).__name__}: {e}", flush=True)
            last = now