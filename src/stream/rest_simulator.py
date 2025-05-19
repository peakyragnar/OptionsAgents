"""
REST API based simulator for options trading data.
Used as a fallback when WebSocket access is not available.
"""
import os, time, asyncio, random
from datetime import datetime
import requests
from dotenv import load_dotenv
from collections import defaultdict

load_dotenv()
API_KEY = os.getenv("POLYGON_KEY")

# Global data stores (same as websocket client)
quotes = {}
pos_long = defaultdict(int)
pos_short = defaultdict(int)

async def fetch_options_chain(ticker="SPX", expiry=None):
    """Fetch options chain for SPX from Polygon REST API."""
    if expiry is None:
        # Get the nearest expiry date
        today = datetime.now().strftime("%Y-%m-%d")
        url = f"https://api.polygon.io/v3/reference/options/contracts?underlying_ticker={ticker}&expiration_date.gte={today}&limit=1000&apiKey={API_KEY}"
    else:
        url = f"https://api.polygon.io/v3/reference/options/contracts?underlying_ticker={ticker}&expiration_date={expiry}&limit=1000&apiKey={API_KEY}"
    
    print(f"Fetching options chain for {ticker}...")
    response = requests.get(url)
    
    if response.status_code == 200:
        data = response.json()
        return data["results"]
    else:
        print(f"Error fetching options: {response.status_code} - {response.text}")
        return []

async def simulate_trading_activity():
    """Simulate trading activity based on REST API data."""
    print("Starting REST API based trading simulation")
    counter = {"quotes": 0, "trades": 0}
    
    while True:
        try:
            # Fetch latest options data
            options = await fetch_options_chain("SPX")
            if not options:
                print("No options data available, retrying in 60s...")
                await asyncio.sleep(60)
                continue
                
            print(f"Fetched {len(options)} option contracts")
            
            # Process each option as a quote
            for option in options[:50]:  # Process first 50 options to avoid API limits
                ticker = option["ticker"]
                
                # Generate simulated bid/ask
                strike = float(option["strike_price"])
                underlying_price = 4200  # Simulated SPX price
                moneyness = abs(strike / underlying_price - 1)
                
                # More realistic bid/ask for options based on moneyness
                mid_price = max(0.5, 10 * (1 - moneyness))
                spread = max(0.05, mid_price * 0.05)  # 5% spread
                
                bid = mid_price - spread/2
                ask = mid_price + spread/2
                
                # Store the quote
                quotes[ticker] = (bid, ask)
                counter["quotes"] += 1
                
                # Log progress
                if counter["quotes"] % 10 == 0:
                    print(f"Processed {counter['quotes']} quotes")
                
                # Simulate some trades (20% chance per option)
                if random.random() < 0.2:
                    # Decide if buy or sell (50/50)
                    is_buy = random.random() < 0.5
                    # Trade size between 1-10 contracts
                    size = random.randint(1, 10)
                    
                    if is_buy:
                        pos_long[ticker] += size
                    else:
                        pos_short[ticker] += size
                        
                    counter["trades"] += 1
                    if counter["trades"] % 5 == 0:
                        print(f"Simulated {counter['trades']} trades")
                
                # Small delay between operations
                await asyncio.sleep(0.1)
            
            # Wait before fetching again (60 seconds to avoid API rate limits)
            print(f"Waiting 60s before next fetch. Current counts: {counter}")
            await asyncio.sleep(60)
            
        except Exception as e:
            print(f"Error in simulation: {e}")
            await asyncio.sleep(30)

async def run_simulator():
    """Run the REST API based simulator."""
    try:
        await simulate_trading_activity()
    except KeyboardInterrupt:
        print("Simulator stopped by user")
    except Exception as e:
        print(f"Simulator error: {e}")

if __name__ == "__main__":
    asyncio.run(run_simulator())