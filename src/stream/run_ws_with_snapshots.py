"""
Run WebSocket client and periodically save intraday dealer gamma snapshots.

This script:
1. Connects to Polygon.io's WebSocket API for options data
2. Processes incoming quotes and trades
3. Saves periodic snapshots of dealer gamma positioning to parquet files
"""
import os, json, asyncio, ssl, datetime
from collections import defaultdict
import websockets
from dotenv import load_dotenv

# Import the websocket client's shared data structures
from src.stream.ws_client import (
    API_KEY, WS_URL, AUTH_MSG, SUB_MSG, PING_MSG,
    quotes, pos_long, pos_short, side_from_price
)

# Import the snapshot function
from src.stream.snapshot_intraday import intraday_snapshot

# Load environment variables
load_dotenv()

# Check if API key is available
if not API_KEY:
    raise SystemExit("POLYGON_KEY missing in environment")

async def take_snapshots():
    """
    Periodically create snapshots of dealer gamma positioning.
    Default is every 5 minutes.
    """
    snapshot_interval = int(os.getenv("SNAPSHOT_INTERVAL_SEC", "300"))  # 5 minutes
    while True:
        await asyncio.sleep(snapshot_interval)
        
        # Count positions
        total_positions = sum(pos_long.values()) + sum(pos_short.values())
        if total_positions == 0:
            print(f"No positions yet, skipping snapshot")
            continue
            
        print(f"\nTaking dealer gamma snapshot...")
        try:
            path = intraday_snapshot()
            if path:
                print(f"Snapshot saved to {path}")
            else:
                print("No snapshot generated (no data available)")
        except Exception as e:
            print(f"Error creating snapshot: {e}")

async def stream_with_snapshots():
    """
    Stream options data from Polygon.io WebSocket API
    and periodically take dealer gamma snapshots.
    """
    ssl_ctx = ssl.create_default_context()
    async with websockets.connect(WS_URL, ssl=ssl_ctx) as ws:
        # 1. Authenticate
        await ws.send(AUTH_MSG)
        while True:
            stat = json.loads(await ws.recv())[0]
            if stat.get("status") == "auth_success":
                print("Authentication successful")
                break
            if stat.get("status") == "auth_failed":
                raise RuntimeError(f"Authentication failed: {stat}")

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
        
        # 2. Subscribe to all options data
        print("Subscribing to all options data...")
        await ws.send(SUB_MSG)
        ack = json.loads(await ws.recv())[0]
        print(f"Subscription response: {ack}")
        
        if ack.get("status") == "success":
            print(f"✓ Successfully subscribed to all options data")
        else:
            raise RuntimeError(f"Failed to subscribe: {ack}")

        # 3. Set up heartbeat task
        async def ping():
            while True:
                await asyncio.sleep(25)
                await ws.send(PING_MSG)
        asyncio.create_task(ping())

        # 4. Set up snapshot task
        snapshot_task = asyncio.create_task(take_snapshots())

        # 5. Set up stats printer
        msg_count = 0
        start_time = asyncio.get_event_loop().time()
        
        async def print_stats():
            while True:
                await asyncio.sleep(10)  # Print stats every 10 seconds
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
        
        stats_task = asyncio.create_task(print_stats())
        
        # 6. Main message processing loop
        print("Starting main message loop - waiting for data...")
        try:
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
        
        except asyncio.CancelledError:
            print("WebSocket connection cancelled")
            # Cancel all tasks
            stats_task.cancel()
            snapshot_task.cancel()
            raise
        
        except Exception as e:
            print(f"WebSocket connection error: {e}")
            stats_task.cancel()
            snapshot_task.cancel()
            raise

if __name__ == "__main__":
    try:
        print("Starting WebSocket client with periodic snapshots")
        asyncio.run(stream_with_snapshots())
    except KeyboardInterrupt:
        print("\nStopped by user")
    except Exception as e:
        print(f"Error: {e}")