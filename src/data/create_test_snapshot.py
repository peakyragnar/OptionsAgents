"""
Create a test snapshot file for SPX options to enable testing.
"""

import pandas as pd
import datetime as dt
import pathlib

# Get today's date in YYYYMMDD format
today = dt.date.today().strftime("%Y%m%d")

# Create basic option symbols
symbols = []
for strike in range(4700, 5300, 50):
    # Call option
    call_symbol = f"O:SPX{today}C{strike:08d}"
    # Put option
    put_symbol = f"O:SPX{today}P{strike:08d}"
    symbols.extend([call_symbol, put_symbol])

# Create a dataframe
df = pd.DataFrame({
    "symbol": symbols,
    "expiration": today
})

# Create output directory
output_dir = pathlib.Path("data/snapshots")
output_dir.mkdir(parents=True, exist_ok=True)

# Save to parquet
output_file = output_dir / f"spx_contracts_{today}.parquet"
df.to_parquet(output_file)

print(f"Created test snapshot with {len(symbols)} symbols at {output_file}")