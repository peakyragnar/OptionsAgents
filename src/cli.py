import asyncio, typer, pathlib
from src.stream.quote_cache import run as quotes_run
from src.stream.trade_feed  import run as trades_run
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
    from src.data.contract_loader import todays_spx_0dte_contracts
    symbols = todays_spx_0dte_contracts(pathlib.Path("data/snapshots"))

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
    df = pd.read_parquet(parquet)
    async def feeder():
        for rec in df.to_dict("records"):
            await trades_run.TRADE_Q.put(rec)
            time.sleep(0.001)
    async def main():
        await asyncio.gather(
            quotes_run(), feeder(), engine_run(append_gamma)
        )
    asyncio.run(main())

if __name__ == "__main__":
    app()