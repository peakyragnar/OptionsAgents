import asyncio, typer, pathlib
from dotenv import load_dotenv
load_dotenv()                    # ← must be before `import stream.quote_cache` etc.
from src.stream.quote_cache import run as quotes_run
from src.stream.trade_feed  import run as trades_run, TRADE_Q
from src.dealer.engine      import run as engine_run
from src.dealer.engine      import _book              # optional inspect
from src.persistence        import append_gamma

app = typer.Typer(add_completion=False, rich_markup_mode="rich")

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
        
        # Filter for realistic strikes only (within +/- 200 points of current SPX)
        print(f"📊 Filtering for realistic strikes around SPX {current_spx:.2f}")
        
        # Calculate strike range (round to nearest 25)
        atm_strike = round(current_spx / 25) * 25
        min_strike = atm_strike - 200  # 200 points below
        max_strike = atm_strike + 200  # 200 points above
        
        print(f"🎯 ATM Strike: {atm_strike}")
        print(f"📈 Strike Range: {min_strike} to {max_strike}")
        
        # Filter dataframe for realistic strikes only
        original_count = len(df)
        df = df[(df['strike'] >= min_strike) & (df['strike'] <= max_strike)]
        filtered_count = len(df)
        
        print(f"✅ Filtered: {original_count} → {filtered_count} options ({original_count - filtered_count} deep OTM removed)")
        
        if filtered_count == 0:
            print("❌ No options found in realistic strike range!")
            return [], current_spx
        
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

@app.command()
def replay(parquet: pathlib.Path):
    """
    Consume a local Parquet of trade prints for offline back-test.
    """
    import pandas as pd, time
    from src.data.mock_quotes import load_mock_quotes
    
    df = pd.read_parquet(parquet)
    print(f"Loaded {len(df)} trades from {parquet}")
    
    # Create a new dataframe with only the required columns if using sample data
    if "ev" in df.columns:
        print("Processing Polygon.io format trades")
    
    async def mock_quotes_run():
        """Instead of fetching quotes from Polygon, use mock data"""
        await load_mock_quotes()
        
        # Just keep the task alive
        while True:
            await asyncio.sleep(1)
    
    async def feeder():
        print(f"Starting trade feed with {len(df)} trades")
        for i, rec in enumerate(df.to_dict("records")):
            await TRADE_Q.put(rec)
            if i % 10 == 0:  # Status update every 10 trades
                print(f"Fed {i}/{len(df)} trades into queue")
            await asyncio.sleep(0.01)  # Slightly longer delay to ensure processing
        print("All trades fed into queue")
        
        # Wait a bit to ensure all trades are processed
        await asyncio.sleep(5)
        print("Replay complete")
            
    async def main():
        await asyncio.gather(
            mock_quotes_run(), feeder(), engine_run(append_gamma)
        )
    asyncio.run(main())

@app.command()
def diagnose():
    """
    Run diagnostic checks on the system to verify data and connections.
    """
    from src.tools.diagnose import run_diagnostics
    run_diagnostics()

@app.command()
def generate_sample():
    """
    Generate a sample trades file for replay testing.
    """
    import importlib.util
    
    # Dynamically import and run the sample generator
    spec = importlib.util.spec_from_file_location(
        "sample_trades", 
        pathlib.Path("data/replays/sample_trades.py")
    )
    sample_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(sample_module)
    
    print("Sample trades file generated successfully")
    print("You can now run: python -m src.cli replay data/replays/sample_trades.parquet")

if __name__ == "__main__":
    app()