"""
Diagnostic tool to check system health and verify data flow
"""

import os
import sys
import pandas as pd
import time
import duckdb
import pathlib
import datetime as dt

# Add project root to path to allow importing from src
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from src.persistence import _DB as DB_PATH, get_latest_gamma, get_gamma_history

def check_parquet_data():
    """Check if we have Parquet data files"""
    parquet_dir = pathlib.Path("data/parquet/spx")
    
    if not parquet_dir.exists():
        print(f"❌ Parquet directory doesn't exist: {parquet_dir}")
        return False
    
    # Find all date directories
    date_dirs = list(parquet_dir.glob("date=*"))
    
    if not date_dirs:
        print(f"❌ No date directories found in {parquet_dir}")
        return False
    
    print(f"✅ Found {len(date_dirs)} date directories")
    
    # Check the latest date directory
    latest_date_dir = sorted(date_dirs)[-1]
    files = list(latest_date_dir.glob("*.parquet"))
    
    if not files:
        print(f"❌ No Parquet files found in {latest_date_dir}")
        return False
    
    latest_file = sorted(files)[-1]
    print(f"✅ Latest Parquet file: {latest_file}")
    
    # Check file contents
    try:
        df = pd.read_parquet(latest_file)
        print(f"✅ Parquet file contains {len(df)} rows")
        print(f"   Columns: {', '.join(df.columns)}")
        
        # Check if gamma values exist and are non-zero
        if 'gamma' in df.columns:
            non_zero_gamma = (df['gamma'] > 0).sum()
            print(f"✅ Found {non_zero_gamma} rows with non-zero gamma values")
        
        return True
    except Exception as e:
        print(f"❌ Error reading Parquet file: {e}")
        return False

def check_duckdb():
    """Check DuckDB database and gamma values"""
    db_path = DB_PATH
    
    if not db_path.exists():
        print(f"❌ DuckDB database doesn't exist: {db_path}")
        return False
    
    try:
        # Use the persistence module functions to safely access the database
        latest_gamma = get_latest_gamma()
        
        if latest_gamma:
            print(f"✅ Latest gamma snapshot found from {latest_gamma['time']}")
            print(f"   Gamma value: {latest_gamma['gamma']}")
            
            # Get history to check for non-zero values
            history = get_gamma_history(limit=100)
            gamma_count = len(history)
            print(f"✅ Found {gamma_count} gamma snapshots in database")
            
            non_zero = (history['dealer_gamma'] != 0).sum()
            print(f"{'✅' if non_zero > 0 else '❌'} Found {non_zero} snapshots with non-zero gamma values")
            
            print("\nLatest gamma values:")
            print(history.head(5))
            
            return non_zero > 0
        else:
            print("❌ No gamma snapshots found in database")
            return False
    except Exception as e:
        print(f"❌ Error checking DuckDB: {e}")
        # Try a more direct approach if the above fails
        try:
            # Create a standalone connection
            db_path_str = str(db_path)
            if os.path.exists(db_path_str):
                # Force a new connection
                con = duckdb.connect(db_path_str + ".diagnostic", read_only=True)
                
                # Attach the actual database as read-only
                con.execute(f"ATTACH '{db_path_str}' AS gamma_db (READ_ONLY)")
                
                # Check tables
                tables = con.execute("SHOW TABLES FROM gamma_db").fetchall()
                if tables:
                    print(f"✅ DuckDB tables: {', '.join(t[0] for t in tables)}")
                else:
                    print("❌ No tables found in database")
                
                # Clean up
                con.close()
                if os.path.exists(db_path_str + ".diagnostic"):
                    os.remove(db_path_str + ".diagnostic")
            else:
                print(f"❌ Database file does not exist: {db_path_str}")
        except Exception as e2:
            print(f"❌ Secondary error checking DuckDB: {e2}")
        
        return False

def check_replay_data():
    """Check if replay data exists"""
    replay_dir = pathlib.Path("data/replays")
    
    if not replay_dir.exists():
        print(f"❌ Replay directory doesn't exist: {replay_dir}")
        return False
    
    parquet_files = list(replay_dir.glob("*.parquet"))
    
    if not parquet_files:
        print(f"❌ No replay Parquet files found in {replay_dir}")
        return False
    
    print(f"✅ Found {len(parquet_files)} replay files:")
    for file in parquet_files:
        try:
            df = pd.read_parquet(file)
            print(f"   - {file.name}: {len(df)} trades")
        except Exception as e:
            print(f"   - {file.name}: Error reading file: {e}")
    
    return True

def run_diagnostics():
    """Run all diagnostic checks"""
    print("=" * 50)
    print(f"Running diagnostics at {dt.datetime.now()}")
    print("=" * 50)
    
    print("\n--- Checking Parquet Data ---")
    check_parquet_data()
    
    print("\n--- Checking DuckDB ---")
    check_duckdb()
    
    print("\n--- Checking Replay Data ---")
    check_replay_data()
    
    print("\n" + "=" * 50)

if __name__ == "__main__":
    run_diagnostics()