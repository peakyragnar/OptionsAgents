"""
Script to fix the symbol format in the snapshot file to match Polygon.io's format.
"""

import pandas as pd
import re
from pathlib import Path
import datetime as dt

def convert_symbol_format(symbol):
    """
    Convert from: O:SPX20250520C00004700
    To:         : O:SPX250520C00004700 (Remove the "20" from the year)
    """
    # Use regex to extract components
    match = re.match(r'O:SPX(\d{4})(\d{4})([CP])(\d+)', symbol)
    if not match:
        print(f"Warning: Could not parse symbol {symbol}")
        return symbol
        
    year, mmdd, cp, strike = match.groups()
    
    # Remove the "20" prefix from the year
    short_year = year[2:]
    
    # Keep the same padding for strike
    
    # Create new symbol in Polygon.io format
    new_symbol = f"O:SPX{short_year}{mmdd}{cp}{strike}"
    return new_symbol

# Get today's date
today = dt.date.today().strftime("%Y%m%d")
snapshot_file = Path(f"data/snapshots/spx_contracts_{today}.parquet")

print(f"Processing snapshot file: {snapshot_file}")

# Read the current snapshot
df = pd.read_parquet(snapshot_file)
print(f"Original symbols (first 5):")
print(df['symbol'].head(5).tolist())

# Convert symbols
df['symbol'] = df['symbol'].apply(convert_symbol_format)
print(f"Converted symbols (first 5):")
print(df['symbol'].head(5).tolist())

# Save back to the file
df.to_parquet(snapshot_file, index=False)
print(f"Updated snapshot file saved")

# Also save a backup of the fixed file
backup_file = Path(f"data/snapshots/spx_contracts_{today}_fixed.parquet")
df.to_parquet(backup_file, index=False)
print(f"Backup saved to: {backup_file}")

print("\nYou can now run the system with the corrected symbols format!")