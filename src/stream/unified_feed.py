"""
Unified WebSocket feed that handles both trades (T.) and quotes (Q.) in a single connection.
This avoids Polygon's connection limit by using one WebSocket for both data types.
"""

import os, json, logging, time, threading, asyncio
from datetime import datetime, timezone
from websocket import WebSocketTimeoutException, WebSocketConnectionClosedException
from .polygon_client import make_ws
from .quote_cache import quote_cache
from .shared_queue import get_trade_queue

_LOG = logging.getLogger("unified_feed")
WS_URL = "wss://socket.polygon.io/options"
PING_INTERVAL = 4  # seconds

def _handle_quote(msg: dict):
    """Handle quote (Q) messages"""
    # Polygon options quotes have these fields:
    # bid, ask, bid_size, ask_size OR bp, ap, bs, as
    bid = msg.get("bid") or msg.get("bp")
    ask = msg.get("ask") or msg.get("ap") 
    
    if not bid or not ask:
        return
    
    # Update the quote cache dictionary
    quote_cache[msg["sym"]] = {
        "bid": float(bid),
        "ask": float(ask),
        "ts": msg.get("t", msg.get("timestamp", 0))
    }
    
    _LOG.debug("Quote %-22s %7.4f × %7.4f",
               msg["sym"], float(bid), float(ask))

def _handle_trade(msg: dict, trade_queue):
    """Handle trade (T) messages"""
    # Get quote for classification
    q = quote_cache.get(msg["sym"])
    
    # Classify trade based on NBBO
    if q:
        px = msg["p"]
        if px >= q["ask"] - 0.01:
            side = "BUY"
        elif px <= q["bid"] + 0.01:
            side = "SELL"
        else:
            side = "?"
    else:
        side = "?"
    
    ts = datetime.fromtimestamp(msg["t"]/1e3, tz=timezone.utc)\
                 .strftime("%H:%M:%S.%f")[:-3]
    
    # Push to trade queue
    trade_msg = {
        "ts": ts,
        "side": side,
        "sym": msg["sym"],
        "price": msg["p"],
        "size": msg["s"],
        "timestamp": msg["t"]/1e3,  # Engine expects float timestamp in seconds
    }
    # Use the passed queue instance
    trade_queue.put_nowait(trade_msg)
    
    # Log every 10th trade with queue size
    global _trade_count
    _trade_count = globals().get('_trade_count', 0) + 1
    if _trade_count % 10 == 0:
        queue_size = trade_queue.qsize()
        print(f"[unified] Pushed trade #{_trade_count} to queue (size={queue_size}): {msg['sym']} {side} {msg['s']}@{msg['p']}")
    
    _LOG.debug("Trade %s %s %s @ %.2f x %d", 
               ts, side, msg["sym"], msg["p"], msg["s"])

def _run_once(symbols: list[str], trade_queue):
    """Run unified feed with both trade and quote subscriptions"""
    # Don't pass symbols to make_ws to prevent auto-subscription
    ws = make_ws(WS_URL, symbols=None)
    
    # Build subscription list with both T. and Q. prefixes
    subscriptions = []
    for sym in symbols:
        subscriptions.append(f"T.{sym}")  # Trades
        subscriptions.append(f"Q.{sym}")  # Quotes
    
    print(f"📡 Unified feed subscribing to {len(subscriptions)} channels ({len(symbols)} symbols x 2)")
    
    # Subscribe in batches
    batch_size = 50
    for i in range(0, len(subscriptions), batch_size):
        batch = subscriptions[i:i+batch_size]
        params = ",".join(batch)
        subscription_msg = {"action": "subscribe", "params": params}
        ws.send(json.dumps(subscription_msg))
        time.sleep(0.1)  # Small delay between batches
    
    print(f"✅ Subscribed to all {len(subscriptions)} channels")
    
    # Keep-alive ping thread
    def _ping(ws):
        while True:
            try:
                ws.send(json.dumps({"action": "ping"}))
                time.sleep(PING_INTERVAL)
            except Exception:
                return
    threading.Thread(target=_ping, args=(ws,), daemon=True).start()
    
    # Main message loop
    msg_count = 0
    quote_count = 0
    trade_count = 0
    
    while True:
        try:
            raw = ws.recv()
            if not raw or raw == "heartbeat":
                continue
            
            frames = json.loads(raw)
            if isinstance(frames, dict):
                frames = [frames]
            
            for msg in frames:
                msg_count += 1
                
                # Handle different message types
                if msg.get("ev") == "Q":  # Quote
                    _handle_quote(msg)
                    quote_count += 1
                    if quote_count % 1000 == 0:
                        print(f"📊 Processed {quote_count:,} quotes, {trade_count:,} trades")
                        
                elif msg.get("ev") == "T":  # Trade
                    _handle_trade(msg, trade_queue)
                    trade_count += 1
                    
                elif msg.get("ev") == "status":
                    status = msg.get("status")
                    if status == "success":
                        _LOG.debug("Subscribed to: %s", msg.get("message", ""))
                    elif status == "error":
                        _LOG.error("Subscription error: %s", msg.get("message"))
                    elif status == "ping":
                        ws.send(json.dumps({"action": "pong"}))
                        
        except WebSocketTimeoutException:
            continue
        except WebSocketConnectionClosedException:
            print("❌ WebSocket connection closed, reconnecting...")
            return
        except Exception as e:
            _LOG.error("WebSocket error: %s", e)
            return

# Async wrapper for CLI integration
async def run(symbols: list[str], delayed: bool = False):
    """Async wrapper for unified feed"""
    # Force queue creation early
    queue = get_trade_queue()
    print(f"[unified] Pre-created queue: {id(queue)} in event loop: {id(asyncio.get_event_loop())}")
    
    while True:
        try:
            _run_once(symbols, queue)
        except Exception as e:
            _LOG.error("Unified feed crashed: %s - reconnecting in 3s", e)
            await asyncio.sleep(3)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    # Test with a few symbols
    test_symbols = ["O:SPXW250530C05900000", "O:SPXW250530P05900000", "I:SPX"]
    asyncio.run(run(test_symbols))