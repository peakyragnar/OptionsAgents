# run_feeds.py  – one-process demo
import os, threading, logging, time, websocket         # add websocket + time
from src.stream import nbbo_feed, trade_feed

logging.basicConfig(level=logging.DEBUG, format="%(asctime)s [%(levelname)s] %(message)s")

# 1️⃣  NBBO quotes in a background thread
def _quotes():
    nbbo_feed.run()        # your existing helper

threading.Thread(target=_quotes, daemon=True).start()

# 2️⃣  trades in the main thread, with auto-reconnect
os.environ.setdefault("TRADE_SUB", "O:SPXW250521C05930000")

while True:
    try:
        trade_feed.run_once()      # blocking call; returns only if socket dies
    except websocket.WebSocketConnectionClosedException as c:
        logging.warning("trade feed closed: %s – reconnecting in 1 s", c)
        time.sleep(1)
    except Exception as e:
        logging.exception("trade feed crash: %s – reconnecting in 1 s", e)
        time.sleep(1)