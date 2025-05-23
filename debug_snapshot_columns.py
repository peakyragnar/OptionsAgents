#!/usr/bin/env python3
"""
Debug snapshot file to see what columns exist
"""

import pandas as pd
from pathlib import Path
from datetime import datetime
import glob

def debug_snapshot_structure():
    """Debug what's actually in your snapshot files"""
    
    print("🔍 DEBUGGING SNAPSHOT STRUCTURE")
    print("="*50)
    
    # Find latest snapshot
    today = datetime.now().strftime("%Y-%m-%d")
    snapshot_dir = Path("data/parquet/spx") / f"date={today}"
    
    if not snapshot_dir.exists():
        print(f"❌ Snapshot directory not found: {snapshot_dir}")
        return
    
    pattern = str(snapshot_dir / "*.parquet")
    files = glob.glob(pattern)
    
    if not files:
        print(f"❌ No parquet files found")
        return
    
    latest_file = max(files, key=lambda f: Path(f).stat().st_mtime)
    print(f"📸 Analyzing: {latest_file}")
    
    try:
        # Load the file
        df = pd.read_parquet(latest_file)
        
        print(f"\n📊 SNAPSHOT INFO:")
        print(f"Rows: {len(df)}")
        print(f"Columns: {list(df.columns)}")
        
        # Show first few rows
        print(f"\n📋 FIRST 3 ROWS:")
        print(df.head(3).to_string())
        
        # Check for different possible symbol columns
        possible_symbol_cols = ['symbol', 'ticker', 'contract', 'underlying_ticker', 'option_symbol']
        
        print(f"\n🔍 LOOKING FOR SYMBOL COLUMNS:")
        for col in possible_symbol_cols:
            if col in df.columns:
                print(f"✅ Found: {col}")
                print(f"   Sample values: {df[col].head(3).tolist()}")
            else:
                print(f"❌ Missing: {col}")
        
        # Check if we can construct symbols from other columns
        required_cols = ['strike', 'expiry', 'option_type']
        has_required = all(col in df.columns for col in required_cols)
        
        print(f"\n🏗️  CAN CONSTRUCT SYMBOLS:")
        print(f"Has required columns {required_cols}: {has_required}")
        
        if has_required:
            print("✅ Can construct symbols from strike/expiry/option_type")
            
            # Show sample constructed symbol
            row = df.iloc[0]
            if 'expiry' in df.columns and 'strike' in df.columns and 'option_type' in df.columns:
                expiry_str = str(row['expiry']).replace('-', '')[-6:]  # YYMMDD
                strike_str = f"{int(row['strike']*1000):08d}"
                symbol = f"O:SPXW{expiry_str}{row['option_type']}{strike_str}"
                print(f"   Sample: {symbol}")
        
        print(f"\n💡 SOLUTION:")
        if 'symbol' in df.columns:
            print("✅ Use 'symbol' column directly")
        elif any(col in df.columns for col in possible_symbol_cols):
            found_col = next(col for col in possible_symbol_cols if col in df.columns)
            print(f"✅ Use '{found_col}' column as symbol")
        elif has_required:
            print("✅ Construct symbols from strike/expiry/option_type")
        else:
            print("❌ Cannot determine symbol format")
            
    except Exception as e:
        print(f"❌ Error reading file: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    debug_snapshot_structure()