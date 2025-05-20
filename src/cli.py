import asyncio, typer, pathlib
from dotenv import load_dotenv
load_dotenv()                    # ← must be before `import stream.quote_cache` etc.

from src.stream.quote_cache import run as quotes_run
from src.stream.trade_feed  import run as trades_run, TRADE_Q
from src.dealer.engine      import run as engine_run
from src.dealer.engine      import _book              # optional inspect
from src.persistence        import append_gamma

app = typer.Typer(add_completion=False, rich_markup_mode="rich")

@app.command()
def live():
    """
    Run quote cache, trade feed, and dealer-gamma engine in real time.
    Snapshots are written to DuckDB every second.
    """
    import os
    from src.data.contract_loader import todays_spx_0dte_contracts
    
    # Set a unique database file for this run to avoid lock conflicts
    os.environ["OA_GAMMA_DB"] = "data/live.db"
    
    # Load today's contracts
    symbols = todays_spx_0dte_contracts(pathlib.Path("data/snapshots"))
    
    if not symbols:
        print("Warning: No symbols loaded. Make sure the snapshot file exists.")
        print("Using test symbols instead...")
        # Add a few test symbols if no real ones are found
        symbols = [
            "O:SPX240520C04800000",
            "O:SPX240520P04800000",
            "O:SPX240520C04900000",
            "O:SPX240520P04900000",
            "O:SPX240520C05000000",
            "O:SPX240520P05000000",
        ]
    
    print(f"Starting live mode with {len(symbols)} symbols")

    async def main():
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