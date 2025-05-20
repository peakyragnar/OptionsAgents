"""
Generate a sample trades parquet file for replay testing.
"""

import pandas as pd
import numpy as np
import os
import datetime as dt
import pathlib

# Create directory for replays if it doesn't exist
replay_dir = pathlib.Path("data/replays")
replay_dir.mkdir(parents=True, exist_ok=True)

# Sample option symbols (these would be actual SPX options in real usage)
symbols = [
    "O:SPX240520C04800000",
    "O:SPX240520P04800000",
    "O:SPX240520C04900000",
    "O:SPX240520P04900000",
    "O:SPX240520C05000000",
    "O:SPX240520P05000000",
]

# Sample trade generation parameters
num_trades = 100
start_time = dt.datetime.now().timestamp() * 1e9  # Nanoseconds since epoch

# Create synthetic trades
trades = []
for i in range(num_trades):
    # Random symbol
    sym = np.random.choice(symbols)
    
    # Random price (more realistic for options)
    price = np.random.uniform(10.0, 100.0)
    
    # Random size (between 1 and 10 contracts)
    size = np.random.randint(1, 11)
    
    # Timestamp (sequential with random gaps)
    timestamp = start_time + i * 1e9 + np.random.randint(0, 1e9)
    
    # Create trade in Polygon.io format
    trade = {
        "ev": "OT",        # Event type: Options Trade
        "sym": sym,        # Option symbol
        "p": price,        # Price
        "s": size,         # Size
        "t": timestamp,    # Timestamp (nanoseconds)
        # Additional fields that might be in real Polygon data
        "c": [0],          # Condition codes
        "x": 4,            # Exchange ID
    }
    trades.append(trade)

# Create DataFrame
df = pd.DataFrame(trades)

# Save to parquet
output_file = replay_dir / "sample_trades.parquet"
df.to_parquet(output_file)
print(f"Created sample trades file: {output_file}")

if __name__ == "__main__":
    print(f"Generated {num_trades} sample trades for replay testing.")