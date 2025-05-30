#!/usr/bin/env python3
"""
Debug parquet schema to understand the data structure
"""

import duckdb
import pandas as pd

def debug_parquet():
    conn = duckdb.connect(':memory:')
    
    print("🔍 Investigating parquet files...\n")
    
    # 1. List all parquet files
    try:
        files = conn.execute("""
            SELECT DISTINCT filename 
            FROM read_parquet('data/parquet/spx/date=*/**.parquet', filename=true)
            LIMIT 5
        """).df()
        print("📁 Sample files:")
        for f in files['filename']:
            print(f"  - {f}")
    except Exception as e:
        print(f"❌ Error listing files: {e}")
    
    # 2. Check schema of a specific file
    print("\n📋 Checking schema of latest file...")
    try:
        # Get the most recent file
        latest_file = 'data/parquet/spx/date=2025-05-29/19_13_17.parquet'
        
        # Read with pandas to see dtypes
        df = pd.read_parquet(latest_file)
        print(f"\nPandas dtypes:")
        print(df.dtypes)
        
        print(f"\nSample data:")
        print(df.head(2))
        
        # Check for problematic columns
        print(f"\nColumn analysis:")
        for col in df.columns:
            null_count = df[col].isna().sum()
            print(f"  {col}: {df[col].dtype}, nulls: {null_count}")
            
    except Exception as e:
        print(f"❌ Error reading with pandas: {e}")
    
    # 3. Try reading with DuckDB column by column
    print("\n🔧 Testing DuckDB column access...")
    try:
        for col in ['strike', 'type', 'bid', 'ask', 'gamma', 'under_px']:
            result = conn.execute(f"""
                SELECT {col} 
                FROM read_parquet('data/parquet/spx/date=2025-05-29/19_13_17.parquet')
                LIMIT 1
            """).fetchone()
            print(f"  {col}: ✅ {result[0]}")
    except Exception as e:
        print(f"  Failed at column: {e}")
    
    # 4. Find the problematic column
    print("\n🔍 Finding problematic columns...")
    all_cols = ['type', 'strike', 'expiry', 'bid', 'ask', 'volume', 
                'open_interest', 'iv', 'delta', 'gamma', 'under_px', 'date']
    
    for col in all_cols:
        try:
            conn.execute(f"""
                SELECT {col} 
                FROM read_parquet('data/parquet/spx/date=2025-05-29/19_13_17.parquet')
                LIMIT 1
            """).fetchone()
            print(f"  {col}: ✅")
        except Exception as e:
            print(f"  {col}: ❌ {e}")
    
    conn.close()

if __name__ == "__main__":
    debug_parquet()