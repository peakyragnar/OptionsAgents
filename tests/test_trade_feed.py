import asyncio, json, pytest, aiohttp
from types import SimpleNamespace
from src.stream.trade_feed import TRADE_Q, run as trade_run

@pytest.mark.asyncio
async def test_trade_feed_pushes(monkeypatch):
    """
    Patch aiohttp so no real socket is opened.
    The fake websocket yields one trade msg then closes.
    """
    # Clear the queue before starting test
    while not TRADE_Q.empty():
        try:
            TRADE_Q.get_nowait()
        except asyncio.QueueEmpty:
            break

    fake_trade = {"sym": "O:SPXW250519P05000000", "p": 1.0, "s": 1, "t": 123}

    class _FakeWS:
        def __init__(self):
            self.closed = False
            self._sent = False
        
        # __aiter__ MUST be a regular method that returns self
        def __aiter__(self):
            return self
            
        # __anext__ must be async and return the next value or raise StopAsyncIteration
        async def __anext__(self):
            if self._sent or self.closed:
                raise StopAsyncIteration
            self._sent = True
            return SimpleNamespace(
                type=aiohttp.WSMsgType.TEXT,
                data=json.dumps([fake_trade])
            )
            
        def exception(self):
            return None
            
        async def close(self):
            self.closed = True

    class _FakeConn:
        async def __aenter__(self):
            return _FakeWS()
            
        async def __aexit__(self, *args):
            pass

    def fake_ws_connect(*args, **kwargs):
        return _FakeConn()

    # Patch the WebSocket connection
    monkeypatch.setattr(aiohttp.ClientSession, "ws_connect", fake_ws_connect)
    # Set environment variable
    monkeypatch.setenv("POLYGON_KEY", "FAKE")

    # Start the trader feed
    task = asyncio.create_task(trade_run(["O:SPXdummy"], delayed=True))
    
    # Give it time to process the message
    await asyncio.sleep(0.5)
    
    # Cancel the task
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass

    # Check that we received the trade
    assert not TRADE_Q.empty(), "Queue is empty, no message was received"
    trade = TRADE_Q.get_nowait()
    assert trade == fake_trade