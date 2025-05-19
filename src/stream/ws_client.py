# ──────────────────────────────────────────────────────────────
# src/stream/ws_client.py   –  clean, minimal, proven working
# ──────────────────────────────────────────────────────────────
import os, json, asyncio, ssl, datetime
from collections import defaultdict
import websockets
from dotenv import load_dotenv

load_dotenv()                                   # reads .env

API_KEY = os.getenv("POLYGON_KEY")
if not API_KEY:
    raise SystemExit("POLYGON_KEY missing in environment")

WS_URL  = os.getenv("POLY_URL",
                    "wss://socket.polygon.io/options")  # real-time

AUTH_MSG = json.dumps({"action": "auth", "params": API_KEY})
SUB_MSG  = json.dumps({"action": "subscribe",
                       "params": "O.*"})   # All options data - simplest format
PING_MSG = json.dumps({"action": "ping"})

# in-memory books ------------------------------------------------
EPS        = 1e-4
quotes     = {}                # ticker → (bid, ask)
pos_long   = defaultdict(int)  # customer buy  (dealer short)
pos_short  = defaultdict(int)  # customer sell (dealer long)
# ----------------------------------------------------------------


def side_from_price(tkr: str, price: float):
    """Return 'buy' | 'sell' | None."""
    bid, ask = quotes.get(tkr, (None, None))
    if bid is None or ask is None:
        return None
    if price >= ask - EPS:
        return "buy"
    if price <= bid + EPS:
        return "sell"
    return None


async def stream():
    ssl_ctx = ssl.create_default_context()
    async with websockets.connect(WS_URL, ssl=ssl_ctx) as ws:
        # 1 AUTH
        await ws.send(AUTH_MSG)
        while True:
            stat = json.loads(await ws.recv())[0]
            if stat.get("status") == "auth_success":
                break
            if stat.get("status") == "auth_failed":
                raise RuntimeError(f"auth failed: {stat}")

        # Check if US markets are open
        now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=-4)))  # US Eastern
        is_weekend = now.weekday() >= 5  # Saturday or Sunday
        is_market_hours = 9 <= now.hour < 16  # 9:00 AM to 4:00 PM ET
        
        if is_weekend:
            print("WARNING: Markets are closed (weekend) - expect no data")
        elif not is_market_hours:
            print(f"WARNING: Markets are closed (current time: {now.hour}:{now.minute} ET) - expect no data")
        else:
            print(f"Markets should be open (current time: {now.hour}:{now.minute} ET)")
        
        # ---- subscribe to all options data ----
        print("Subscribing to all options data...")
        
        # Use the simplest format possible
        await ws.send(SUB_MSG)
        ack = json.loads(await ws.recv())[0]
        print(f"Subscription response: {ack}")
        
        if ack.get("status") == "success":
            print(f"✓ Successfully subscribed to all options data")
        else:
            raise RuntimeError(f"Failed to subscribe: {ack}")

        # 3 heartbeat
        async def ping():
            while True:
                await asyncio.sleep(25)
                await ws.send(PING_MSG)
        asyncio.create_task(ping())

        # 4 main loop
        print("Starting main message loop - waiting for data...")
        msg_count = 0
        start_time = asyncio.get_event_loop().time()
        
        # Print stats every 10 seconds
        async def print_stats():
            while True:
                await asyncio.sleep(10)
                elapsed = asyncio.get_event_loop().time() - start_time
                print(f"\n--- STATS after {int(elapsed)}s ---")
                print(f"Messages received: {msg_count}")
                print(f"Quotes cached: {len(quotes)}")
                print(f"Customer buys: {sum(pos_long.values())}")
                print(f"Customer sells: {sum(pos_short.values())}")
                
                # Show a few samples if we have any
                if quotes:
                    print("\nSample quotes:")
                    for i, (sym, (bid, ask)) in enumerate(list(quotes.items())[:3]):
                        print(f"  {sym}: bid={bid}, ask={ask}")
                        
                if pos_long or pos_short:
                    print("\nSample positions:")
                    if pos_long:
                        for i, (sym, qty) in enumerate(list(pos_long.items())[:2]):
                            print(f"  LONG: {sym} = {qty}")
                    if pos_short:
                        for i, (sym, qty) in enumerate(list(pos_short.items())[:2]):
                            print(f"  SHORT: {sym} = {qty}")
                
                print("---------------------------")
        
        # Start the stats printer
        stats_task = asyncio.create_task(print_stats())
        
        async for raw in ws:
            msg_count += 1
            if msg_count <= 5:  # Only print the first few messages
                print(f"MSG #{msg_count}: {raw[:100]}...")
            
            try:
                messages = json.loads(raw)
                for m in messages:
                    # Get message type
                    ev = m.get("ev")
                    
                    # Handle quote message
                    if ev == "Q":  # Basic quote
                        quotes[m["sym"]] = (m.get("bp", 0), m.get("ap", 0))
                    
                    # Handle trade message and update positions
                    elif ev == "T":  # Basic trade
                        sym = m.get("sym", "")
                        # Only process options (symbols start with O:)
                        if sym.startswith("O:"):
                            side = side_from_price(sym, m.get("p", 0))
                            size = m.get("s", 0)
                            
                            if side == "buy":
                                pos_long[sym] += size
                            elif side == "sell":
                                pos_short[sym] += size
            
            except Exception as e:
                if msg_count <= 10:  # Only print errors for the first few messages
                    print(f"Error processing message: {e}")


if __name__ == "__main__":
    asyncio.run(stream())