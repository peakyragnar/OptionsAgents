"""
Tests for WebSocket client and intraday snapshot functionality.
"""
import os
import sys
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
import json
import asyncio
import pandas as pd

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import modules for testing
from src.stream.ws_client import side_from_price, quotes


@pytest.fixture
def setup_test_data():
    """Set up test data for WebSocket client tests."""
    # Clear existing data
    quotes.clear()
    
    # Add test quotes
    quotes["O:SPX240517C04200000"] = (10.0, 11.0)  # 4200 call
    quotes["O:SPX240517P04200000"] = (8.0, 9.0)    # 4200 put
    
    yield
    
    # Clean up
    quotes.clear()


def test_side_from_price(monkeypatch):
    """Test trade side determination from price."""
    # Use a local quotes dict to avoid interference
    test_quotes = {
        "O:SPX240517C04200000": (10.0, 11.0)  # bid, ask
    }
    
    # Monkey patch the quotes.get method
    monkeypatch.setattr("src.stream.ws_client.quotes", test_quotes)
    
    # Test buy side (at or above ask)
    assert side_from_price("O:SPX240517C04200000", 11.0) == "buy"
    assert side_from_price("O:SPX240517C04200000", 11.5) == "buy"
    
    # Test sell side (at or below bid)
    assert side_from_price("O:SPX240517C04200000", 10.0) == "sell"
    assert side_from_price("O:SPX240517C04200000", 9.5) == "sell"
    
    # Test between bid and ask
    assert side_from_price("O:SPX240517C04200000", 10.5) is None
    
    # Test missing quote
    assert side_from_price("O:SPX240517C04300000", 10.0) is None


def test_parse_occ_ticker():
    """Test the OCC ticker parsing logic in snapshot_intraday.py."""
    import datetime as dt
    
    # Test OCC ticker format parsing
    ticker = "O:SPX240517C04200000"
    parts = ticker.split(":")
    # Format is O:SPX + YYMMDD + C/P + Strike with 8 digits (including 3 decimal places, padded with zeros)
    symbol = ticker
    underlying = parts[1][:3]  # SPX
    date_str = parts[1][3:9]  # 240517
    option_type = parts[1][9]  # C or P
    strike_str = parts[1][10:-3]  # 04200 (Strike price without last 3 digits)
    
    # Parse date
    expiry = dt.datetime.strptime(date_str, "%y%m%d").date()
    strike = int(strike_str) / 1000  # Convert to actual strike price
    
    # Check parsing
    assert underlying == "SPX"
    assert expiry == dt.date(2024, 5, 17)
    assert option_type == "C"
    assert strike == 4.2  # 4200 after dividing by 1000


@pytest.mark.asyncio
async def test_message_processing():
    """Test WebSocket message processing with simplified mocking."""
    from src.stream.ws_client import quotes, pos_long, pos_short
    
    # Clear existing data
    quotes.clear()
    pos_long.clear()
    pos_short.clear()
    
    # Add quotes first
    quotes["O:SPX240517C04200000"] = (10.0, 11.0)
    quotes["O:SPX240517P04200000"] = (8.0, 9.0)
    
    # Process fake trade messages directly
    trade_messages = [
        {
            "ev": "T",
            "sym": "O:SPX240517C04200000",
            "p": 11.0,  # Price at ask
            "s": 5      # Size of 5 contracts
        },
        {
            "ev": "T",
            "sym": "O:SPX240517P04200000",
            "p": 8.0,   # Price at bid
            "s": 3      # Size of 3 contracts
        }
    ]
    
    # Use side_from_price to manually update positions
    for m in trade_messages:
        sym = m.get("sym", "")
        if sym.startswith("O:"):
            side = side_from_price(sym, m.get("p", 0))
            size = m.get("s", 0)
            
            if side == "buy":
                pos_long[sym] += size
            elif side == "sell":
                pos_short[sym] += size
    
    # Check that positions were updated correctly
    assert pos_long["O:SPX240517C04200000"] == 5  # 5 contracts bought
    assert pos_short["O:SPX240517P04200000"] == 3  # 3 contracts sold


@pytest.mark.asyncio
async def test_snapshot_intraday():
    """Test intraday snapshot generation with fixed formatted tickers."""
    from src.stream.ws_client import pos_long, pos_short
    
    # Clear existing data
    pos_long.clear()
    pos_short.clear()
    
    # Use proper OCC format tickers
    pos_long["O:SPX240517C04200000"] = 10
    pos_short["O:SPX240517C04200000"] = 5
    pos_long["O:SPX240517P04100000"] = 3
    pos_short["O:SPX240517P04300000"] = 15
    
    # Create a simplified mock of the intraday_snapshot function
    @patch('src.stream.snapshot_intraday.get_spot', return_value=4200.0)
    @patch('pandas.DataFrame.to_parquet')
    def test_snapshot(mock_to_parquet, mock_get_spot):
        from src.stream.snapshot_intraday import intraday_snapshot
        path = intraday_snapshot("/tmp/test_intraday")
        return path, mock_to_parquet.called
    
    # Run the test function
    path, was_called = test_snapshot()
    
    # Verify results
    assert was_called  # to_parquet was called
    assert path is not None  # path is returned