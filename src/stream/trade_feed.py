# ---------- src/stream/trade_feed.py ----------
"""
Proof-of-concept trade feed.
  • subscribes to ONE option contract (env TRADE_SUB)
  • looks up latest quote in quote_cache
  • prints side-inferred trade
Run:  TRADE_SUB='O:SPXW250521C05930000' PYTHONPATH=. python -m src.stream.trade_feed --debug
"""

import os, json, logging, time, threading, websocket, zoneinfo
from datetime     import datetime, timezone
from websocket    import WebSocketTimeoutException
from .polygon_client import make_ws
from .quote_cache    import quote_cache
from src.polygon_helpers import fetch_spx_chain

_LOG = logging.getLogger("trade_feed")
WS_URL       = "wss://socket.polygon.io/options"
PING_SECONDS = 25

def _infer_side(trd: dict, q: dict | None) -> str:
    "Return 'BUY' | 'SELL' | '?'  using last cached NBBO."
    if not q:
        return "?"
    px = trd["p"]
    if px >= q["ask"] - 0.01:      # equity opts: ½-penny tick ok
        return "BUY"
    if px <= q["bid"] + 0.01:
        return "SELL"
    return "?"

def run_once():
    today = datetime.now(zoneinfo.ZoneInfo("US/Eastern")).strftime("%Y-%m-%d")
    tickers = fetch_spx_chain(today)          # ~400-600 tickers
    params   = ",".join(tickers)

    ws = make_ws(WS_URL)
    ws.send(json.dumps({"action":"subscribe", "params": params}))
    _LOG.info("listening for trades on %d tickers …", len(tickers))
    
    # Set longer timeouts for stability
    ws.settimeout(20)
    ws.sock.settimeout(20)          # some versions need this too

    # keep-alive pings (Polygon kills idle sockets ~60 s)
    def _ping(ws):
        """Background thread: send {"action":"ping"} every 2 s and WebSocket ping every 10s."""
        while True:
            try:
                # Send application-level ping
                ws.send(json.dumps({"action": "ping"}))
                time.sleep(2)
                
                # Every 5 cycles (10s), send a WebSocket protocol-level ping
                if int(time.time()) % 10 == 0:
                    ws.ping()
                    
            except Exception as e:          # socket closed – just exit thread, main loop will reconnect
                logging.debug("ping thread exit: %s", e)
                return
    threading.Thread(target=_ping, args=(ws,), daemon=True).start()
    
    # Hand-rolled loop lets us swallow timeouts
    while True:
        try:
            # Use recv directly instead of for-loop iteration
            raw = ws.recv()
            
            # Skip empty frames or heartbeats
            if not raw or raw == "heartbeat":
                continue
                
            # Process the message
            for msg in json.loads(raw):               # Polygon wraps in list
                if msg.get("ev") != "T":              # just in case
                    continue
                q = quote_cache.get(msg["sym"])       # may be None
                side = _infer_side(msg, q)
                ts   = datetime.fromtimestamp(msg["t"]/1e3, tz=timezone.utc)\
                                .strftime("%H:%M:%S.%f")[:-3]

                print(f"{ts}  {side:4s}  {msg['sym']:22s} "
                      f"{msg['p']:8.2f}  x{msg['s']}")
                      
        except WebSocketTimeoutException:
            # Normal timeout - just continue waiting
            continue
        except Exception:
            _LOG.exception("bad trade msg")

# --------------------------------------------------------------------------- #
if __name__ == "__main__":
    import argparse, logging
    ap = argparse.ArgumentParser()
    ap.add_argument("--debug", action="store_true")
    args = ap.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    while True:
        try:
            run_once()          # reconnect-forever loop
        except KeyboardInterrupt:
            raise
        except Exception as exc:
            _LOG.error("WS crashed: %s — reconnecting in 3 s", exc)
            time.sleep(3)