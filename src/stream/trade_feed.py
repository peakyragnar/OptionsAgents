# ---------- src/stream/trade_feed.py ----------
"""
Enhanced trade feed with SPX index support.
  • subscribes to SPX options AND SPX index (I:SPX)
  • processes both option trades and index updates
  • updates pin detector with real-time SPX level
"""

import os, json, logging, time, threading, websocket, zoneinfo, asyncio
from datetime     import datetime, timezone
from websocket    import WebSocketTimeoutException
from .polygon_client import make_ws
from .quote_cache    import quote_cache
from src.polygon_helpers import fetch_spx_chain

_LOG = logging.getLogger("trade_feed")
WS_URL       = "wss://socket.polygon.io/options"
PING_SECONDS = 25

# Global variables for SPX tracking and pin detection
CURRENT_SPX_LEVEL = 5850.0
LAST_SPX_UPDATE = None
PIN_DETECTOR = None

def initialize_pin_detector():
    """Initialize the pin detector for real-time updates"""
    global PIN_DETECTOR
    try:
        from src.dealer.pin_detector import ZeroDTEPinDetector
        PIN_DETECTOR = ZeroDTEPinDetector()
        print("✅ Pin detector initialized in trade feed")
        return True
    except ImportError:
        print("⚠️  Pin detector not available")
        return False

def process_spx_index_update(message: dict):
    """
    Process SPX index updates from WebSocket
    
    Expected formats:
    - Aggregate: {"ev": "AM", "sym": "I:SPX", "c": 5786.25, ...}
    - Value: {"ev": "V", "sym": "I:SPX", "val": 5786.25, ...}
    """
    global CURRENT_SPX_LEVEL, LAST_SPX_UPDATE, PIN_DETECTOR
    
    try:
        if message.get("sym") != "I:SPX":
            return False  # Not an SPX message
            
        # Extract SPX price from different message types
        spx_price = None
        
        if message.get("ev") == "AM":  # Aggregate message
            spx_price = message.get("c")  # Close price
        elif message.get("ev") == "V":  # Value message
            spx_price = message.get("val")  # Value
        elif message.get("ev") == "A":  # Another aggregate format
            spx_price = message.get("c") or message.get("close")
            
        if spx_price and spx_price > 0:
            old_spx = CURRENT_SPX_LEVEL
            CURRENT_SPX_LEVEL = float(spx_price)
            LAST_SPX_UPDATE = datetime.now()
            
            # Update pin detector if available
            if PIN_DETECTOR:
                PIN_DETECTOR.current_spx = CURRENT_SPX_LEVEL
                
            # Print SPX updates (but not too frequently)
            spx_change = CURRENT_SPX_LEVEL - old_spx
            if abs(spx_change) > 0.25:  # Only print if meaningful change
                print(f"📊 SPX: {CURRENT_SPX_LEVEL:.2f} ({spx_change:+.2f})")
            
            return True
            
    except Exception as e:
        _LOG.error(f"Error processing SPX update: {e}")
        
    return False

def process_options_trade(message: dict):
    """Process options trade message"""
    try:
        q = quote_cache.get(message["sym"])       # may be None
        side = _infer_side(message, q)
        ts = datetime.fromtimestamp(message["t"]/1e3, tz=timezone.utc)\
                        .strftime("%H:%M:%S.%f")[:-3]

        print(f"{ts}  {side:4s}  {message['sym']:22s} "
              f"{message['p']:8.2f}  x{message['s']}")

        # Push the trade into the queue for dealer engine
        TRADE_Q.put_nowait({
            "ts": ts,
            "side": side,
            "sym": message["sym"],
            "price": message["p"],
            "size": message["s"],
            "timestamp": datetime.fromtimestamp(message["t"]/1e3, tz=timezone.utc),
        })
        
        # Also process for pin detector if available
        if PIN_DETECTOR and message["sym"].startswith("O:SPX"):
            try:
                from src.dealer.pin_detector import Trade
                
                # Parse strike and option type from symbol
                # Format: O:SPXW250523C05850000
                symbol = message["sym"]
                if len(symbol) >= 21:
                    option_type = symbol[-9]  # C or P
                    strike_str = symbol[-8:]  # 05850000
                    strike = float(strike_str) / 1000  # Convert to actual strike
                    
                    # Create Trade object
                    trade = Trade(
                        symbol=symbol,
                        strike=strike,
                        option_type=option_type,
                        price=message["p"],
                        size=message["s"],
                        timestamp=datetime.fromtimestamp(message["t"]/1e3, tz=timezone.utc),
                        side=side,
                        is_premium_seller=False  # Will be determined by detector
                    )
                    
                    # Get NBBO for classification
                    nbbo_bid = q.get("bid", 0) if q else 0
                    nbbo_ask = q.get("ask", 0) if q else 0
                    
                    # Process through pin detector
                    PIN_DETECTOR.process_trade(trade, nbbo_bid, nbbo_ask)
                    
            except Exception as e:
                _LOG.debug(f"Pin detector processing error: {e}")
        
    except Exception as e:
        _LOG.error(f"Error processing options trade: {e}")

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

def _run_once(tickers: list[str] | None = None):
    # Initialize pin detector
    initialize_pin_detector()
    
    if tickers:                   # unit-test path
        syms = tickers
    else:                        # normal path
        today = datetime.now(zoneinfo.ZoneInfo("US/Eastern")).strftime("%Y-%m-%d")
        syms = fetch_spx_chain(today)          # ~400-600 tickers
    
    # Add SPX index if not already present
    if "I:SPX" not in syms:
        syms.append("I:SPX")
        print(f"✅ Added I:SPX to subscription list")
    
    params = ",".join(syms)
    print(f"📡 Subscribing to {len(syms)} symbols ({len([s for s in syms if s.startswith('O:')])} options + {len([s for s in syms if s.startswith('I:')])} indices)")

    ws = make_ws(WS_URL)
    ws.send(json.dumps({"action":"subscribe", "params": params}))
    _LOG.info("listening for trades/updates on %d tickers …", len(syms))
    
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
                
                # Handle SPX index updates
                if msg.get("sym") == "I:SPX":
                    if process_spx_index_update(msg):
                        continue  # Successfully processed SPX update
                
                # Handle options trades
                if msg.get("ev") == "T":              # Trade event
                    process_options_trade(msg)
                    
                # Handle other message types if needed
                elif msg.get("ev") in ["AM", "V", "A"] and msg.get("sym") == "I:SPX":
                    # Additional SPX message formats
                    process_spx_index_update(msg)
                      
        except WebSocketTimeoutException:
            # Normal timeout - just continue waiting
            continue
        except Exception:
            _LOG.exception("bad message processing")

# Print pin status periodically
def print_pin_status():
    """Print current pin detection status"""
    if PIN_DETECTOR:
        try:
            summary = PIN_DETECTOR.get_pin_summary()
            if summary['total_active_strikes'] > 0:
                print(f"\n🎯 Pin Status: SPX {summary['current_spx']:.2f} | "
                      f"Strongest: {summary['strongest_pin']['strike']} "
                      f"(${summary['strongest_pin']['strength']:,.0f}) | "
                      f"Risk: {summary['risk_level']} | "
                      f"Strikes: {summary['total_active_strikes']}")
                
                if summary['recent_alerts']:
                    for alert in summary['recent_alerts'][:2]:  # Show max 2 alerts
                        print(f"  ⚠️  {alert}")
        except Exception as e:
            _LOG.debug(f"Pin status error: {e}")

# Set up periodic pin status reporting
_last_pin_report = 0

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
    
    # Initialize pin detector
    initialize_pin_detector()
    
    while True:
        try:
            _run_once()          # reconnect-forever loop
        except KeyboardInterrupt:
            if PIN_DETECTOR:
                print(f"\n🎯 Final Pin Status:")
                print_pin_status()
            raise
        except Exception as exc:
            _LOG.error("WS crashed: %s — reconnecting in 3 s", exc)
            time.sleep(3)

# --------------------------------------------------------------------------- #
# compatibility helpers for unit-tests

# switch to async queue so dealer.engine can await it
TRADE_Q: "asyncio.Queue[dict]" = asyncio.Queue()

# ---------------------------------------------------------------- #
# Back-compat wrapper used by tests
async def run(tickers: list[str], delayed: bool = False):
    """
    Wrapper expected by tests:
      • accepts ticker list
      • runs synchronously for now
    """
    _run_once(tickers)

# Expose run_once for backward compatibility
def run_once():
    _run_once()

# New function to get current SPX level
def get_current_spx() -> float:
    """Get the current SPX level from real-time feed"""
    return CURRENT_SPX_LEVEL

def get_pin_detector():
    """Get the current pin detector instance"""
    return PIN_DETECTOR