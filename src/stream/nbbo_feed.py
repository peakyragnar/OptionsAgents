# ------------------------------------  imports / constants  -------------
import os, json, logging, threading, time
from datetime import datetime, timezone
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

    q = { _POLY_TO_GENERIC[k]: msg[k] for k in _POLY_TO_GENERIC if k in msg }
    if "bid" not in q or "ask" not in q:        # incomplete quote
        return

    quote_cache.update(symbol = msg["sym"],
                       ts     = msg["t"],
                       **q)

    _LOG.debug("Quote %-22s %7.4f × %7.4f  %s",
               msg["sym"], q["bid"], q["ask"],
               datetime.fromtimestamp(msg["t"]/1e3, tz=timezone.utc)
                        .strftime("%H:%M:%S.%f")[:-3])

# ------------------------------------------------------------------------
WS_URL = "wss://socket.polygon.io/options"

def _run_ws():
    ws = make_ws(WS_URL)

    # Subscribe -------------------------------------------------------------
    ws.send(json.dumps({                       # must arrive <5 s after auth
        "action": "subscribe",
        "params": os.getenv("NBBO_SUBS", "Q.*")
    }))
    
    #  🔑  FIRST KEEP-ALIVE IMMEDIATELY  🔑
    ws.send('{"action":"ping"}')
    
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

    for raw in ws:                       # each websocket frame
        if not raw:
            continue                     # <-- keep this simple guard

        try:
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

                if msg.get("ev") != "Q":          # skip anything not NBBO
                    continue

                # Use the correct Polygon field names
                quote_cache.update(
                    symbol   = msg["sym"],
                    bid      = msg["bp"],          # <-- bp
                    bid_size = msg["bs"],          # <-- bs
                    ask      = msg["ap"],          # <-- ap
                    ask_size = msg["as"],          # <-- as
                    ts       = msg["t"],
                )
                _LOG.debug(
                    "Quote %-22s %7.2f × %7.2f  %s",
                    msg["sym"], msg["bp"], msg["ap"],
                    datetime.fromtimestamp(msg["t"]/1e3, tz=timezone.utc)
                            .strftime("%H:%M:%S.%f")[:-3],
                )
        except json.JSONDecodeError:
            _LOG.debug("non-JSON frame: %r", raw)
        except Exception:
            _LOG.exception("bad quote msg")

# ------------------------------------------------------------------------
def run():
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