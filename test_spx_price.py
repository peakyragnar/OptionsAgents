#!/usr/bin/env python3
"""Test SPX price fetching"""

import os
from polygon import RESTClient
from datetime import date, timedelta
from dotenv import load_dotenv

# Load environment
load_dotenv()

# Get API key
api_key = os.getenv("POLYGON_KEY")
if not api_key:
    print("❌ No POLYGON_KEY found")
    exit(1)

print(f"✅ Using API key: {api_key[:8]}...")

# Create client
client = RESTClient(api_key)

# Test 1: Try I:SPX
print("\n🔍 Testing I:SPX ticker:")
try:
    end_date = date.today()
    start_date = end_date - timedelta(days=5)
    
    aggs = client.get_aggs(
        ticker="I:SPX",
        multiplier=1,
        timespan="day",
        from_=start_date.strftime('%Y-%m-%d'),
        to=end_date.strftime('%Y-%m-%d'),
        adjusted=True
    )
    
    results = list(aggs)
    if results:
        latest = results[-1]
        print(f"✅ Got SPX data: close=${latest.close}")
        print(f"   Date: {latest.timestamp}")
        print(f"   High: ${latest.high}")
        print(f"   Low: ${latest.low}")
    else:
        print("❌ No results for I:SPX")
        
except Exception as e:
    print(f"❌ Error getting I:SPX: {e}")

# Test 2: Try snapshot API
print("\n🔍 Testing snapshot API:")
try:
    response = client.get_snapshot_all("indices")
    if hasattr(response, 'tickers'):
        for ticker in response.tickers[:5]:  # First 5
            if 'SPX' in ticker.ticker:
                print(f"   Found: {ticker.ticker} = ${ticker.day.close if hasattr(ticker.day, 'close') else 'N/A'}")
except Exception as e:
    print(f"❌ Error getting snapshot: {e}")

# Test 3: Try previous close
print("\n🔍 Testing previous close:")
try:
    prev_close = client.get_previous_close("I:SPX")
    if hasattr(prev_close, 'results') and prev_close.results:
        result = prev_close.results[0]
        print(f"✅ Previous close: ${result.c}")
        print(f"   Volume: {result.v}")
except Exception as e:
    print(f"❌ Error getting previous close: {e}")