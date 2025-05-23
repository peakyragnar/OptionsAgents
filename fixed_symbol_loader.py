def load_symbols_from_snapshot():
    """
    Symbol loader customized for your snapshot format
    Columns: ['type', 'strike', 'expiry', 'bid', 'ask', 'volume', 'open_interest', 'iv', 'gamma', 'vega', 'theta', 'delta', 'under_px']
    """
    import pandas as pd
    import glob
    from datetime import datetime
    from pathlib import Path
    import os
    
    try:
        # Find latest snapshot
        today = datetime.now().strftime("%Y-%m-%d")
        snapshot_dir = Path("data/parquet/spx") / f"date={today}"
        
        if not snapshot_dir.exists():
            print(f"❌ Snapshot directory not found: {snapshot_dir}")
            return [], None
        
        pattern = str(snapshot_dir / "*.parquet")
        files = glob.glob(pattern)
        
        if not files:
            print(f"❌ No parquet files found")
            return [], None
        
        latest_file = max(files, key=os.path.getctime)
        print(f"📸 Loading symbols from: {latest_file}")
        
        df = pd.read_parquet(latest_file)
        print(f"✅ Loaded {len(df)} rows")
        
        # Extract real SPX price from under_px column
        current_spx = df['under_px'].iloc[0] if 'under_px' in df.columns else 5800.0
        print(f"📊 Real SPX level from snapshot: {current_spx}")
        
        # Required columns for symbol construction
        required_cols = ['strike', 'expiry', 'type']  # Note: 'type' not 'option_type'
        
        if not all(col in df.columns for col in required_cols):
            print(f"❌ Missing required columns. Have: {list(df.columns)}")
            return [], current_spx
        
        print("✅ Constructing symbols from strike/expiry/type")
        
        symbols = []
        for _, row in df.iterrows():
            try:
                strike = float(row['strike'])
                expiry = str(row['expiry'])
                option_type = str(row['type']).upper()  # 'type' column, not 'option_type'
                
                # Skip if invalid data
                if strike <= 0 or option_type not in ['C', 'P']:
                    continue
                
                # Convert expiry to YYMMDD format
                if '-' in expiry:  # 2025-05-23 format
                    expiry_date = pd.to_datetime(expiry)
                    expiry_str = expiry_date.strftime("%y%m%d")  # 250523
                else:
                    expiry_str = expiry[-6:]  # Last 6 chars
                
                # Format strike as 8-digit integer (multiply by 1000)
                strike_str = f"{int(strike * 1000):08d}"
                
                # Construct symbol: O:SPXW250523C05850000
                symbol = f"O:SPXW{expiry_str}{option_type}{strike_str}"
                symbols.append(symbol)
                
            except Exception as e:
                print(f"⚠️  Error constructing symbol for strike {row.get('strike', 'unknown')}: {e}")
                continue
        
        print(f"✅ Constructed {len(symbols)} symbols")
        
        # Show sample symbols
        if symbols:
            print(f"Sample symbols: {symbols[:5]}...")
        
        return symbols, current_spx
        
    except Exception as e:
        print(f"❌ Error loading symbols: {e}")
        import traceback
        traceback.print_exc()
        return [], None


# Updated CLI live command
@app.command()
def live():
    """
    Run quote cache, trade feed, and dealer-gamma engine in real time.
    Snapshots are written to DuckDB every second.
    """
    import os
    
    # Set a unique database file for this run to avoid lock conflicts
    os.environ["OA_GAMMA_DB"] = "data/live.db"
    
    # Load symbols using the fixed loader
    symbols, real_spx_price = load_symbols_from_snapshot()
    
    if not symbols:
        print("❌ CRITICAL: No symbols available! Cannot run live mode.")
        print("Solutions:")
        print("1. Check that snapshots are running: python -m src.ingest.snapshot")
        print("2. Check snapshot directory: ls -la data/parquet/spx/")
        print("3. Verify snapshot has data: python debug_snapshot_columns.py")
        return
    
    # ADD SPX INDEX TO SYMBOL LIST FOR REAL-TIME PRICING
    if "I:SPX" not in symbols:
        symbols.append("I:SPX")
        print(f"✅ Added SPX index (I:SPX) to symbol list")
    
    print(f"🚀 Starting live mode with {len(symbols)} symbols")
    options_count = len([s for s in symbols if s.startswith('O:')])
    index_count = len([s for s in symbols if s.startswith('I:')])
    print(f"   📊 {options_count} options + {index_count} indices")
    
    # Show real SPX level
    if real_spx_price:
        print(f"   📈 Snapshot SPX level: {real_spx_price:.2f}")
    
    async def main():
        # Initialize pin detector if available
        try:
            from src.dealer.pin_detector import ZeroDTEPinDetector
            pin_detector = ZeroDTEPinDetector()
            
            # Set initial SPX level from snapshot
            if real_spx_price:
                pin_detector.current_spx = real_spx_price
                print(f"✅ Pin detector initialized with SPX {real_spx_price:.2f}")
            else:
                print("✅ Pin detector initialized with default SPX level")
            
            # Load gamma surface from snapshot data
            try:
                from datetime import datetime
                import pandas as pd
                import glob
                from pathlib import Path
                
                today = datetime.now().strftime("%Y-%m-%d")
                snapshot_dir = Path("data/parquet/spx") / f"date={today}"
                pattern = str(snapshot_dir / "*.parquet")
                files = glob.glob(pattern)
                
                if files:
                    latest_file = max(files, key=os.path.getctime)
                    df = pd.read_parquet(latest_file)
                    
                    # Convert to options chain format using correct column names
                    options_chain = []
                    for _, row in df.iterrows():
                        if row['strike'] > 0 and row['type'] in ['C', 'P']:
                            option_data = {
                                'strike': row['strike'],
                                'option_type': row['type'],  # Using 'type' column
                                'gamma': row.get('gamma', 0),
                                'bid': row.get('bid', 0),
                                'ask': row.get('ask', 0)
                            }
                            options_chain.append(option_data)
                    
                    pin_detector.update_gamma_surface(options_chain)
                    print(f"🎯 Pin detector gamma surface updated with {len(options_chain)} options")
                        
            except Exception as e:
                print(f"⚠️  Could not initialize pin detector gamma surface: {e}")
            
        except ImportError:
            print("⚠️  Pin detector not available - running without pin detection")
        
        # Run the main streaming components
        await asyncio.gather(
            quotes_run(),
            trades_run(symbols),
            engine_run(append_gamma),
        )
    
    asyncio.run(main())