import asyncio, pytest, time

pytestmark = pytest.mark.asyncio

async def test_quote_cache_populates():
    import importlib
    qc = importlib.import_module("src.stream.quote_cache")

    # start poller but stop it after ~2 s
    task = asyncio.create_task(qc.run())
    await asyncio.sleep(2)
    task.cancel()

    assert qc.quotes, "no quotes captured"
    # pick one sample and sanity-check bid < ask
    bid, ask, _ = next(iter(qc.quotes.values()))
    assert bid < ask