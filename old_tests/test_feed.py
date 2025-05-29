#!/usr/bin/env python
import asyncio, time
from src.stream import ws_client as w        # uses existing listener

async def main():
    # Start the WebSocket stream
    stream_task = asyncio.create_task(w.stream())
    
    # Check data at multiple intervals
    for wait_time in [5, 10, 20, 30]:
        await asyncio.sleep(5)  # Wait in 5-second increments
        # Print current status
        print(f"\n--- After {wait_time} seconds ---")
        print("quotes cached  :", len(w.quotes))
        print("customer buys  :", sum(w.pos_long.values()))
        print("customer sells :", sum(w.pos_short.values()))
        
        # List a few quotes if we have any
        if len(w.quotes) > 0:
            print("\nSample quotes:")
            for i, (symbol, (bid, ask)) in enumerate(list(w.quotes.items())[:3]):
                print(f"  {symbol}: bid={bid}, ask={ask}")
                
        # List some buy/sell positions if we have any
        if sum(w.pos_long.values()) > 0:
            print("\nSample buys:")
            for i, (symbol, amount) in enumerate(list(w.pos_long.items())[:3]):
                print(f"  {symbol}: {amount} contracts")
                
        if sum(w.pos_short.values()) > 0:
            print("\nSample sells:")
            for i, (symbol, amount) in enumerate(list(w.pos_short.items())[:3]):
                print(f"  {symbol}: {amount} contracts")

if __name__ == "__main__":
    asyncio.run(main())