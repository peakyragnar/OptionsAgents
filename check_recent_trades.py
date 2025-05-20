"""
Check if there are recent trades for SPX options using the REST API.
This helps verify if there are actually trades happening that we should be receiving.
"""

import os
import requests
import datetime as dt
import json
from dotenv import load_dotenv
load_dotenv()

def check_trades():
    # Get API key
    api_key = os.environ.get("POLYGON_KEY", "")
    
    # Get current date
    today = dt.datetime.now().strftime("%Y-%m-%d")
    
    # Pick a few SPX options to check
    test_symbols = [
        "O:SPX240520C04800000",
        "O:SPX240520P04800000",
        "O:SPX240520C04900000",
        "O:SPX240520P04900000",
        "O:SPX240520C05000000",
        "O:SPX240520P05000000",
    ]
    
    print(f"Checking for recent trades today ({today})...")
    print("=" * 60)
    
    for symbol in test_symbols:
        # Make REST API call to get recent trades
        url = f"https://api.polygon.io/v3/trades/{symbol}"
        params = {
            "timestamp": f"{today}",
            "limit": 10,
            "apiKey": api_key
        }
        
        print(f"Checking trades for {symbol}...")
        response = requests.get(url, params=params)
        
        if response.status_code == 200:
            data = response.json()
            trades = data.get("results", [])
            
            if trades:
                print(f"✓ Found {len(trades)} trades today for {symbol}")
                # Print details of the first trade
                first_trade = trades[0]
                trade_time = dt.datetime.fromtimestamp(first_trade.get("t", 0) / 1e9).strftime("%H:%M:%S")
                print(f"  Most recent: {trade_time}, Price: {first_trade.get('p')}, Size: {first_trade.get('s')}")
            else:
                print(f"✗ No trades found today for {symbol}")
        else:
            print(f"✗ Error {response.status_code}: {response.text}")
    
    print("\nAlso checking for trades in the whole SPX option chain...")
    
    # Try to get ANY SPX option trades (broader search)
    url = "https://api.polygon.io/v3/trades"
    params = {
        "ticker.prefix": "O:SPX",
        "timestamp": f"{today}",
        "limit": 10,
        "apiKey": api_key
    }
    
    response = requests.get(url, params=params)
    
    if response.status_code == 200:
        data = response.json()
        trades = data.get("results", [])
        
        if trades:
            print(f"✓ Found {len(trades)} trades today for SPX options")
            print("Recent SPX option trades:")
            for trade in trades:
                symbol = trade.get("T", "")
                trade_time = dt.datetime.fromtimestamp(trade.get("t", 0) / 1e9).strftime("%H:%M:%S")
                print(f"  {symbol} at {trade_time}, Price: {trade.get('p')}, Size: {trade.get('s')}")
        else:
            print("✗ No SPX option trades found today")
    else:
        print(f"✗ Error with broader search: {response.status_code}: {response.text}")
    
    print("\nTrade check complete.")

if __name__ == "__main__":
    check_trades()