#!/usr/bin/env python
"""Test the live dealer gamma from the database"""
from src.persistence import get_latest_gamma, get_gamma_history

# Get latest gamma
latest = get_latest_gamma()
if latest:
    print(f"=== Live Dealer Gamma ===")
    print(f"Time: {latest['time']}")
    print(f"Total Dealer Gamma: ${latest['gamma']:,.2f}")
    print(f"Raw value: {latest['gamma']}")
else:
    print("No gamma data found")

# Get history
print("\n=== Gamma History (last 20) ===")
history = get_gamma_history(limit=20)
if not history.empty:
    # Show unique gamma values
    unique_gammas = history['dealer_gamma'].unique()
    print(f"Unique gamma values: {len(unique_gammas)}")
    for gamma in unique_gammas[:5]:  # Show first 5 unique values
        print(f"  ${gamma:,.2f}")
    
    # Show time range
    print(f"\nTime range: {history['time'].min()} to {history['time'].max()}")
    print(f"Total snapshots: {len(history)}")
else:
    print("No history found")

# Check if dealer engine is still running
import subprocess
result = subprocess.run(['ps', 'aux'], capture_output=True, text=True)
if 'src.cli live' in result.stdout:
    print("\n✅ Dealer engine is running")
else:
    print("\n❌ Dealer engine is NOT running")