# ---------- src/stream/nbbo_feed.py ----------
"""
Live NBBO (quote) feed for options.
Keeps quote_cache filled so trade_feed can compute greeks / dealer-gamma.
"""

import json, logging, threading, time
from datetime import datetime, timezone
from .polygon_client import make_ws          # already provided in repo
from .quote_cache      import quote_cache    # in src/stream/quote_cache.py

_LOG = logging.getLogger("nbbo_feed")

# 1. Make the websocket --------------------------------------------------------
WS_URL = "wss://socket.polygon.io/options"   # correct URL for options WS

def _run_ws():
    ws = make_ws(WS_URL)

    # Subscribe to the NBBO channel (see Polygon docs)
    ws.send(json.dumps({"action": "subscribe", "params": "NO.*"}))

    # -------------------------------------------------------------------------
    for raw in ws:            # blocks; yields each received message
        try:
            msg = json.loads(raw)[0]         # Polygon wraps in a list
            if msg["ev"] != "NO":            # not an NBBO message
                continue

            # Example message fields:  sym, bid, bs, ask, asz, t (unix-ms)
            quote_cache.update(
                symbol   = msg["sym"],
                bid      = msg["bid"],
                bid_size = msg["bs"],
                ask      = msg["ask"],
                ask_size = msg["as"],
                ts       = msg["t"],
            )
            if _LOG.isEnabledFor(logging.DEBUG):
                _LOG.debug(
                    "Quote %-18s %7.2f × %7.2f (%s)",
                    msg["sym"], msg["bid"], msg["ask"],
                    datetime.fromtimestamp(msg["t"]/1e3, tz=timezone.utc)
                           .strftime("%H:%M:%S.%f")[:-3]
                )

        except Exception as exc:
            _LOG.exception("bad quote msg: %s", exc)

def run():
    """Start the websocket in the current thread (blocks)."""
    _LOG.info("starting NBBO websocket…")
    while True:         # simple reconnect-forever loop
        try:
            _run_ws()
        except Exception as exc:
            _LOG.error("WS crashed: %s — reconnecting in 3 s", exc)
            time.sleep(3)

# If you `python -m src.stream.nbbo_feed` directly -----------------------------
if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    run()