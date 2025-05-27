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
from src.directional_pin_detector import DIRECTIONAL_PIN_DETECTOR
from src.enhanced_pin_detection import (
    initialize_enhanced_pin_detector,
    process_trade_for_pin_detection,
    should_trigger_analysis,
    generate_pin_analysis,
    get_current_spx_level,
    get_quick_status
)


_LOG = logging.getLogger("trade_feed")
WS_URL       = "wss://socket.polygon.io/options"
PING_SECONDS = 25

# Add this function to get SPX level from your existing quote cache
def get_current_spx_from_quotes():
    """Get current SPX level from your existing quote cache"""
    try:
        # Try different SPX symbol formats that your system might use
        spx_symbols = ['I:SPX', 'SPX', '$SPX', 'SPXW']
        
        for symbol in spx_symbols:
            if symbol in quote_cache:
                q = quote_cache.get(symbol)
                if q and 'bid' in q and 'ask' in q:
                    bid = q['bid']
                    ask = q['ask']
                    if bid > 0 and ask > 0:
                        spx_level = (bid + ask) / 2
                        print(f"🔍 SPX from quotes ({symbol}): {spx_level:.2f}")
                        return spx_level
                    
    except Exception as e:
        print(f"⚠️  Error getting SPX from quotes: {e}")
    
    # Fallback: try to get from Polygon API
    return get_spx_from_polygon()

def get_spx_from_polygon():
    """Fallback to get SPX from Polygon API"""
    try:
        import requests
        
        api_key = os.getenv('POLYGON_KEY')
        if not api_key:
            print("⚠️  No POLYGON_KEY found")
            return 5900.0  # Default fallback
            
        url = f"https://api.polygon.io/v2/last/nbbo/I:SPX"
        headers = {"Authorization": f"Bearer {api_key}"}
        
        response = requests.get(url, headers=headers, timeout=5)
        data = response.json()
        
        if 'results' in data and data['results']:
            bid = data['results'].get('bid', 0)
            ask = data['results'].get('ask', 0)
            if bid > 0 and ask > 0:
                spx_level = (bid + ask) / 2
                print(f"🔍 SPX from Polygon API: {spx_level:.2f}")
                return spx_level
                
    except Exception as e:
        print(f"⚠️  Error fetching SPX from API: {e}")
    
    # Final fallback - use global tracking variable
    if CURRENT_SPX_LEVEL > 0:
        return CURRENT_SPX_LEVEL
    
    # Final fallback
    print("⚠️  Using default SPX level: 5900.0")
    return 5900.0

# Global variables for SPX tracking and pin detection
CURRENT_SPX_LEVEL = 5850.0
LAST_SPX_UPDATE = None
PIN_DETECTOR = None
_last_pin_report = time.time()  # Track last pin status report time
_last_directional_pin_report = time.time()  # Track last directional pin report time
_trade_counter = 0  # Track number of trades processed
_enhanced_trade_counter = 0  # Track trades for enhanced pin detector

def initialize_pin_detector():
    """Initialize the pin detector for real-time updates"""
    global PIN_DETECTOR
    # Use the global DIRECTIONAL_PIN_DETECTOR instance
    PIN_DETECTOR = DIRECTIONAL_PIN_DETECTOR
    print("✅ Directional pin detector initialized in trade feed")
    return True

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
            
            # Update directional pin detector with SPX level
            DIRECTIONAL_PIN_DETECTOR.update_spx_level(CURRENT_SPX_LEVEL)
                
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
                # Process through pin detector using the format it expects
                PIN_DETECTOR.process_trade({
                    'symbol': message["sym"],
                    'price': message["p"],
                    'size': message["s"],
                    'timestamp': message["t"],
                    'conditions': message.get("c", [])
                })
                
                # ADD THIS SECTION:
                global _trade_counter, _last_pin_report
                _trade_counter += 1
                current_time = time.time()
                
                # Show pin analysis every 100 trades OR every 2 minutes
                if _trade_counter % 100 == 0 or (current_time - _last_pin_report > 120):
                    # Get current SPX level from multiple sources
                    def get_reliable_spx():
                        # Try quote cache first
                        spx_quote = quote_cache.get('I:SPX') or quote_cache.get('SPX')
                        if spx_quote:
                            bid = spx_quote.get('bid', 0)
                            ask = spx_quote.get('ask', 0)
                            if bid and ask:
                                return (bid + ask) / 2
                        
                        # Fallback: use last known SPX level
                        return CURRENT_SPX_LEVEL
                    
                    # Update before analysis
                    current_spx = get_reliable_spx()
                    PIN_DETECTOR.update_spx_level(current_spx)
                    
                    print(f"\n🎯 PIN ANALYSIS UPDATE (Trade #{_trade_counter}):")
                    PIN_DETECTOR.print_human_dashboard()  # Use PIN_DETECTOR, not DIRECTIONAL_PIN_DETECTOR
                    _last_pin_report = current_time
                    
            except Exception as e:
                pass  # Silent error handling
        
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
    
    # Initialize enhanced pin detector
    print("🎯 Initializing Enhanced Pin Detection System...")
    initialize_enhanced_pin_detector("data/live_enhanced_pins.db")
    
    if tickers:                   # unit-test path
        syms = tickers
    else:                        # normal path - REALISTIC STRIKES
        # Get current SPX level from your snapshot system
        try:
            from src.cli import load_symbols_from_snapshot
            _, real_spx_price = load_symbols_from_snapshot()
            current_spx = real_spx_price if real_spx_price else 5800
            print(f"📊 Using real SPX level: {current_spx:.2f}")
            # Update directional pin detector with SPX level
            update_pin_detector_with_spx_level(current_spx)
        except:
            current_spx = 5800  # Fallback
            print(f"📊 Using fallback SPX level: {current_spx}")
            # Update directional pin detector with SPX level
            update_pin_detector_with_spx_level(current_spx)
        
        # Round to nearest 25 (SPX strikes are typically in 25-point increments)
        atm_strike = round(current_spx / 25) * 25
        
        # Generate strikes: 75 above and 75 below ATM
        strikes = []
        for i in range(-75, 76):  # -75 to +75 = 151 strikes
            strike = atm_strike + (i * 25)  # 25-point increments
            if strike > 0:  # Only positive strikes
                strikes.append(strike)
        
        print(f"📊 SPX Level: {current_spx:.2f}")
        print(f"🎯 ATM Strike: {atm_strike}")  
        print(f"📈 Strike Range: {min(strikes)} to {max(strikes)} ({len(strikes)} strikes)")
        
        # Build SPXW symbols for today's expiry
        today = datetime.now(zoneinfo.ZoneInfo("US/Eastern")).strftime("%Y-%m-%d")
        exp_str = datetime.now(zoneinfo.ZoneInfo("US/Eastern")).strftime("%y%m%d")  # YYMMDD format
        
        syms = []
        
        # Add calls and puts for each strike
        for strike in strikes:
            strike_str = f"{strike:08.0f}"  # 8-digit format: 05800000
            call_symbol = f"O:SPXW{exp_str}C{strike_str}"
            put_symbol = f"O:SPXW{exp_str}P{strike_str}"
            syms.extend([call_symbol, put_symbol])
        
        print(f"✅ Generated {len(syms)} SPXW options")
        print(f"📝 Sample symbols: {syms[:5]}...")
        print(f"🎯 ATM Call: O:SPXW{exp_str}C{atm_strike:08.0f}")
        print(f"🎯 ATM Put:  O:SPXW{exp_str}P{atm_strike:08.0f}")
    
    # Add SPX index if not already present
    if "I:SPX" not in syms:
        syms.append("I:SPX")
        print(f"✅ Added I:SPX to subscription list")
    
    params = ",".join(syms)
    print(f"📡 Subscribing to {len(syms)} symbols ({len([s for s in syms if s.startswith('O:')])} options + {len([s for s in syms if s.startswith('I:')])} indices)")

    ws = make_ws(WS_URL, syms)
    
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
            for msg in json.loads(raw):
                
                # Handle authentication success - subscribe after auth
                if msg.get("ev") == "status" and msg.get("status") == "auth_success":
                    # Authentication successful - subscription handled in polygon_client.py
                    _LOG.info("Authentication successful")
                    continue
                
                # Handle SPX index updates
                if msg.get("sym") == "I:SPX":
                    if process_spx_index_update(msg):
                        continue  # Successfully processed SPX update
                
                # Handle options trades
                if msg.get("ev") == "T":              # Trade event
                    process_options_trade(msg)
                    
                    # Process through enhanced pin detector
                    global _enhanced_trade_counter
                    _enhanced_trade_counter += 1
                    
                    # Get current SPX level from multiple sources
                    current_spx = get_current_spx_from_quotes()
                    
                    # Process through enhanced pin detector
                    try:
                        process_trade_for_pin_detection(msg, current_spx)
                        
                        # Generate analysis periodically using enhanced triggering
                        if should_trigger_enhanced_analysis(_enhanced_trade_counter):
                            print("\n" + "="*90)
                            print("🎯 ENHANCED PIN ANALYSIS TRIGGERED")
                            print("="*90)
                            analysis = generate_pin_analysis()
                            print(analysis)
                            print("="*90 + "\n")
                        
                        # Quick status every 500 trades
                        elif _enhanced_trade_counter % 500 == 0:
                            status = get_quick_status()
                            print(f"📊 Quick Status (Trade #{_enhanced_trade_counter}): Confidence {status.get('total_confidence', 0):.1%}, SPX {status.get('spx_level', 0):.2f}")
                            
                    except Exception as e:
                        _LOG.debug(f"Enhanced pin detector error: {e}")
                    
                # Handle other message types if needed
                elif msg.get("ev") in ["AM", "V", "A"] and msg.get("sym") == "I:SPX":
                    # Additional SPX message formats
                    process_spx_index_update(msg)
                      
        except WebSocketTimeoutException:
            # Normal timeout - just continue waiting
            # Print pin status every few minutes
            global _last_pin_report, _last_directional_pin_report
            current_time = time.time()
            if current_time - _last_pin_report > 120:  # Every 2 minutes
                print_pin_status()
                _last_pin_report = current_time
            
            # Print directional pin dashboard every 1 minute
            if current_time - _last_directional_pin_report > 60:  # Every 1 minute
                # Get current SPX level from multiple sources
                def get_reliable_spx():
                    # Try quote cache first
                    spx_quote = quote_cache.get('I:SPX') or quote_cache.get('SPX')
                    if spx_quote:
                        bid = spx_quote.get('bid', 0)
                        ask = spx_quote.get('ask', 0)
                        if bid and ask:
                            return (bid + ask) / 2
                    
                    # Fallback: use last known SPX level
                    return CURRENT_SPX_LEVEL
                
                # Update before analysis
                current_spx = get_reliable_spx()
                DIRECTIONAL_PIN_DETECTOR.update_spx_level(current_spx)
                
                DIRECTIONAL_PIN_DETECTOR.print_human_dashboard()
                _last_directional_pin_report = current_time
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

# Enhanced analysis frequency function
def should_trigger_enhanced_analysis(trade_count: int) -> bool:
    """
    Smart triggering for enhanced analysis
    More frequent during high activity periods
    """
    from datetime import timedelta
    
    # Base frequency: every 100 trades
    if trade_count % 100 == 0:
        return True
        
    # High frequency during market hours
    now = datetime.now(zoneinfo.ZoneInfo("US/Eastern"))
    market_open = now.replace(hour=9, minute=30)
    market_close = now.replace(hour=16, minute=0)
    
    if market_open <= now <= market_close:
        # Every 50 trades during regular market hours
        if trade_count % 50 == 0:
            return True
            
        # Every 25 trades in last 30 minutes of trading
        last_30_min = market_close - timedelta(minutes=30)
        if now >= last_30_min and trade_count % 25 == 0:
            return True
    
    return False

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

def update_pin_detector_with_spx_level(spx_level: float):
    """Update pin detector with current SPX level from snapshot"""
    DIRECTIONAL_PIN_DETECTOR.update_spx_level(spx_level)