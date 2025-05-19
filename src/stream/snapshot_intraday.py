"""
Every N minutes, build a strike-level table of dealer positions
established *so far today* and write to Parquet.
"""
import datetime as dt, pathlib, pandas as pd, math, os, re

# Import from websocket client or REST simulator based on environment
if os.getenv("USE_REST", "").lower() in ("true", "1", "yes"):
    # Using REST simulator
    from src.stream.rest_simulator import pos_long, pos_short, quotes
else:
    # Using WebSocket client
    from src.stream.ws_client import pos_long, pos_short, quotes

from src.utils.greeks import bs_greeks

def get_spot():
    """Get the current SPX spot price."""
    try:
        # reuse your aggregate-close call from snapshot.py
        from polygon import RESTClient
        import os, dotenv
        dotenv.load_dotenv()
        spot = RESTClient(os.getenv("POLYGON_KEY")).get_previous_close("I:SPX").close
        return float(spot)
    except Exception as e:
        print(f"Error getting spot price: {e}")
        # Fallback to a reasonable SPX value
        return 4200.0

def parse_occ_ticker(ticker):
    """
    Parse OCC ticker format 'O:SPX240517C04200000' into components.
    
    Returns:
        (expiry_date, option_type, strike_price)
    """
    if not ticker.startswith("O:"):
        return None, None, None
    
    # Use regex pattern for OCC format
    pattern = r"O:([A-Z]+)(\d{6})([CP])(\d+)"
    match = re.match(pattern, ticker)
    
    if not match:
        return None, None, None
    
    underlying, date_str, option_type, strike_str = match.groups()
    
    # Parse date (yymmdd)
    try:
        expiry = dt.datetime.strptime(date_str, "%y%m%d").date()
        # Parse strike with decimal places (last 3 digits are decimal places)
        strike = int(strike_str[:-3]) / 1000
        return expiry, option_type, strike
    except (ValueError, IndexError) as e:
        print(f"Error parsing ticker {ticker}: {e}")
        return None, None, None

def intraday_snapshot(path="data/intraday"):
    """
    Create a snapshot of current dealer gamma positioning.
    
    Args:
        path: Directory to save snapshot parquet file
        
    Returns:
        Path to created file or None if no data
    """
    rows, spot = [], get_spot()
    today = dt.date.today()
    
    print(f"Creating snapshot with {len(pos_long)} long and {len(pos_short)} short positions")
    print(f"Using spot price: {spot}")

    for tkr in set(pos_long) | set(pos_short):
        if not tkr.startswith("O:SPX"):         # skip non-SPX
            continue
            
        net_dealer = pos_short[tkr] - pos_long[tkr]   # +ve dealer long
        if net_dealer == 0:
            continue

        # parse OCC ticker using improved function
        expiry, typ, strike = parse_occ_ticker(tkr)
        
        if None in (expiry, typ, strike):
            print(f"Warning: Could not parse ticker {tkr}, skipping")
            continue
            
        # Calculate time to expiry in years
        tau = max((expiry - today).days, 1) / 365
        
        # Use placeholder IV (can be improved with historical data)
        iv = 0.20
        
        # Calculate gamma
        gamma, _, _ = bs_greeks(spot, strike, iv, tau, typ)
        
        # Calculate notional gamma (scaled by 10k for readability)
        gamma_usd = -gamma * net_dealer * spot**2 / 10_000

        rows.append({
            "strike": strike, 
            "type": typ,
            "dealer_pos": net_dealer, 
            "gamma_usd": gamma_usd,
            "symbol": tkr,
            "days_to_expiry": (expiry - today).days
        })

    if not rows:
        print("No rows generated for snapshot")
        return None
        
    # Create dataframe and sort by strike
    df = pd.DataFrame(rows)
    df = df.sort_values("strike")
    
    # Generate timestamp and path
    ts = dt.datetime.now()
    out = pathlib.Path(path)/f"{ts:%H_%M_%S}.parquet"
    out.parent.mkdir(parents=True, exist_ok=True)
    
    # Print summary stats
    print(f"Writing snapshot with {len(df)} positions")
    print(f"Total dealer gamma: ${df['gamma_usd'].sum():.2f}k")
    
    # Save to parquet
    df.to_parquet(out, compression="zstd")
    return out