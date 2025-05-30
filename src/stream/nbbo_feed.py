# ------------------------------------  imports / constants  -------------
import os, json, logging, threading, time
from datetime import datetime, timezone
from websocket import WebSocketTimeoutException
from .polygon_client import make_ws
from .quote_cache      import quote_cache

PING_INTERVAL = 4            # seconds  (<5 s keeps Polygon happy)
_POLY_TO_GENERIC = {        # bp/bp → bid/ask   (added earlier)
    "bp": "bid",    "bs": "bid_size",
    "ap": "ask",    "as": "ask_size",
}

_LOG = logging.getLogger("nbbo_feed")

# ------------------------------------------------------------------------
def _handle(msg: dict):
    """Convert Polygon Q-message → quote_cache entry."""
    if msg.get("ev") != "Q":
        return                          # ignore anything that isn't a quote
    
    # Polygon options quotes have these fields:
    # bid, ask, bid_size, ask_size OR bp, ap, bs, as
    bid = msg.get("bid") or msg.get("bp")
    ask = msg.get("ask") or msg.get("ap") 
    
    if not bid or not ask:
        # Debug first quote to see structure
        if not hasattr(_handle, '_debug_shown'):
            print(f"[NBBO] First quote structure: {msg}")
            _handle._debug_shown = True
        return
    
    # Update the quote cache dictionary
    quote_cache[msg["sym"]] = {
        "bid": float(bid),
        "ask": float(ask),
        "ts": msg.get("t", msg.get("timestamp", 0))
    }

    _LOG.debug("Quote %-22s %7.4f × %7.4f  %s",
               msg["sym"], float(bid), float(ask),
               datetime.fromtimestamp(msg.get("t", 0)/1e3, tz=timezone.utc)
                        .strftime("%H:%M:%S.%f")[:-3])

# ------------------------------------------------------------------------
WS_URL = "wss://socket.polygon.io/options"

def _run_ws():
    # Don't pass symbols to make_ws to prevent auto-subscription to trades
    ws = make_ws(WS_URL, symbols=None)

    # Subscribe -------------------------------------------------------------
    subscription = os.getenv("NBBO_SUBS", "Q.*")
    symbols = subscription.split(',')
    print(f"[NBBO] Total symbols to subscribe: {len(symbols)}")
    
    # Subscribe in batches of 50 to avoid overwhelming Polygon
    batch_size = 50
    for i in range(0, len(symbols), batch_size):
        batch = symbols[i:i+batch_size]
        batch_subscription = ",".join(batch)
        
        subscription_msg = {
            "action": "subscribe",
            "params": batch_subscription
        }
        
        print(f"[NBBO] Subscribing batch {i//batch_size + 1}/{(len(symbols)-1)//batch_size + 1} ({len(batch)} symbols)")
        ws.send(json.dumps(subscription_msg))
        time.sleep(0.1)  # Small delay between batches
    
    _LOG.info(f"Sent all NBBO subscriptions in {(len(symbols)-1)//batch_size + 1} batches")
    
    #  🔑  FIRST KEEP-ALIVE IMMEDIATELY  🔑
    ws.send('{"action":"ping"}')
    
    print("[NBBO] Starting message receive loop...")
    
    # ------------------------------------------------------------------ #
    #   Keep-alive: send additional pings every 4 seconds               #
    # ------------------------------------------------------------------ #
    def _keep_alive():
        while True:
            try:
                ws.send('{"action":"ping"}')
            except Exception:
                break                      # socket closed
            time.sleep(PING_INTERVAL)     # 4-second heartbeat
    _keep_alive_thread = threading.Thread(target=_keep_alive, daemon=True)
    _keep_alive_thread.start()

    # Use recv() like trade_feed does, not iterator
    while True:
        try:
            raw = ws.recv()
            
            if not raw:
                continue
                
            frames = json.loads(raw)
            if isinstance(frames, dict):
                frames = [frames]

            for msg in frames:

                # ---------- NEW HEARTBEAT HANDLER ----------------
                # Polygon sends: {"ev":"status","message":"ping"}
                if msg.get("ev") == "status" and msg.get("message") == "ping":
                    ws.send(json.dumps({"action": "pong"}))   # reply
                    continue
                # ------------------------------------------------

                # Use the _handle function which properly maps fields
                try:
                    _handle(msg)
                except Exception as e:
                    # Log first error only to avoid spam
                    if not hasattr(_run_ws, '_error_logged'):
                        print(f"[NBBO] Error in _handle: {e}")
                        print(f"[NBBO] Message was: {msg}")
                        _run_ws._error_logged = True
        except WebSocketTimeoutException:
            continue  # Normal timeout, just continue
        except json.JSONDecodeError:
            _LOG.debug("non-JSON frame: %r", raw)
        except Exception as e:
            _LOG.exception("bad quote msg: %s", e)
            break  # Exit loop on serious errors

# ------------------------------------------------------------------------
def run(symbols=None):
    """Run NBBO feed with optional symbol list"""
    if symbols:
        # Subscribe to quotes for the specific symbols from snapshot
        # Format: Q.O:SPXW250530C05900000,Q.O:SPXW250530P05900000,Q.I:SPX
        quote_symbols = [f"Q.{sym}" for sym in symbols]
        subscription = ",".join(quote_symbols)
        os.environ["NBBO_SUBS"] = subscription
        _LOG.info(f"NBBO subscribing to {len(symbols)} specific symbols from snapshot")
    
    _LOG.info("starting NBBO websocket…")
    while True:
        try:
            _run_ws()
        except Exception as exc:
            _LOG.error("WS crashed: %s — reconnecting in 3 s", exc)
            time.sleep(3)

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG,
                        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    run()