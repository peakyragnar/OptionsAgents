"""
Script to check the official format of option symbols from Polygon.io API.
"""

import os
import requests
import json
from dotenv import load_dotenv
load_dotenv()

# Get API key from environment
api_key = os.environ.get("POLYGON_KEY", "")

# Query options for SPX (S&P 500 index)
url = "https://api.polygon.io/v3/reference/options/contracts"
params = {
    "underlying_ticker": "SPX",
    "limit": 10,
    "apiKey": api_key
}

print(f"Querying Polygon.io API for SPX option contracts...")
response = requests.get(url, params=params)

if response.status_code == 200:
    data = response.json()
    contracts = data.get("results", [])
    
    if contracts:
        print(f"Found {len(contracts)} contracts")
        print("\nSample contract details:")
        for i, contract in enumerate(contracts[:5]):
            print(f"\nContract {i+1}:")
            print(f"Ticker: {contract.get('ticker')}")
            print(f"Underlying: {contract.get('underlying_ticker')}")
            print(f"Expiration: {contract.get('expiration_date')}")
            print(f"Strike: {contract.get('strike_price')}")
            print(f"Call/Put: {contract.get('contract_type')}")
    else:
        print("No contracts found")
else:
    print(f"Error: {response.status_code}, {response.text}")

# Now check the option chain snapshot to see ticker formats
print("\n\nChecking option chain snapshot...")
snapshot_url = "https://api.polygon.io/v3/snapshot/options/SPX"
snapshot_params = {
    "apiKey": api_key
}

snapshot_response = requests.get(snapshot_url, params=snapshot_params)

if snapshot_response.status_code == 200:
    snapshot_data = snapshot_response.json()
    if "results" in snapshot_data:
        options = snapshot_data.get("results", {}).get("options", [])
        if options:
            print(f"Found {len(options)} options in snapshot")
            print("\nSample option tickers from snapshot:")
            for i, option in enumerate(options[:10]):
                print(f"{option.get('ticker')}")
        else:
            print("No options found in snapshot")
    else:
        print(f"No results in snapshot response: {snapshot_data}")
else:
    print(f"Snapshot error: {snapshot_response.status_code}, {snapshot_response.text}")