"""
Generate mock quotes data for the quote cache during replay testing.
"""

import asyncio
from src.stream.quote_cache import quotes

async def load_mock_quotes():
    """Load mock quotes for testing."""
    # SPX options for the sample replay data
    symbols = [
        "O:SPX240520C04800000",
        "O:SPX240520P04800000",
        "O:SPX240520C04900000",
        "O:SPX240520P04900000",
        "O:SPX240520C05000000",
        "O:SPX240520P05000000",
    ]
    
    current_time = int(asyncio.get_event_loop().time() * 1e9)  # Current time in nanoseconds
    
    # Generate reasonable bid/ask prices based on strike and option type
    for sym in symbols:
        if sym.endswith("C04800000"):  # 4800 call
            bid, ask = 189.5, 190.5
        elif sym.endswith("P04800000"):  # 4800 put
            bid, ask = 84.25, 85.50
        elif sym.endswith("C04900000"):  # 4900 call
            bid, ask = 112.75, 113.75
        elif sym.endswith("P04900000"):  # 4900 put
            bid, ask = 107.25, 108.50
        elif sym.endswith("C05000000"):  # 5000 call
            bid, ask = 49.50, 50.75
        elif sym.endswith("P05000000"):  # 5000 put
            bid, ask = 142.75, 144.00
        else:
            bid, ask = 50.0, 55.0  # Generic fallback
        
        # Add to quotes cache
        quotes[sym] = (bid, ask, current_time)
    
    print(f"Loaded {len(symbols)} mock quotes into cache")
    return quotes