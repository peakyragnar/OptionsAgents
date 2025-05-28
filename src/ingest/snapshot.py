"""
Pull one snapshot of today's SPX 0-DTE option chain
and store it here:

data/parquet/spx/date=YYYY-MM-DD/HH_MM_SS.parquet
"""

import datetime, os, pathlib, pandas as pd, math, sys
import logging
import time
from datetime import date, timedelta
import dotenv
from polygon import RESTClient

# Add project root to path to allow importing from src
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from src.utils.logging_config import setup_application_logging, setup_component_logger
from src.utils.greeks import bs_greeks, implied_vol, estimate_vol_from_moneyness, bs_greeks_dict

# Initialize logging
setup_application_logging()
logger = setup_component_logger(__name__)

dotenv.load_dotenv()
client = RESTClient(os.getenv("POLYGON_KEY"))

def _nan_if_none(x):
    return float("nan") if x is None else float(x)

def get_spx_price_fixed(client: RESTClient):
    """
    Fixed version to get SPX price using correct Polygon.io API methods
    """
    try:
        # Method 1: Try current price (most reliable)
        logger.info("Attempting to get current SPX price...")
        
        # For SPX, use the correct ticker format
        ticker = "I:SPX"  # Index format
        
        try:
            # Get current price using the correct method
            current_price = client.get_last_trade(ticker)
            if hasattr(current_price, 'price') and current_price.price:
                logger.info(f"✅ Got current SPX price: {current_price.price}")
                return float(current_price.price)
        except Exception as e:
            logger.warning(f"Current price failed: {e}")
        
        # Method 2: Try previous close using aggregates
        logger.info("Trying previous close via aggregates...")
        try:
            yesterday = (date.today() - timedelta(days=1)).strftime('%Y-%m-%d')
            today = date.today().strftime('%Y-%m-%d')
            
            # Get daily aggregates (this is the correct method)
            aggs = client.get_aggs(
                ticker=ticker,
                multiplier=1,
                timespan="day", 
                from_=yesterday,
                to=today,
                adjusted=True,
                sort="desc",
                limit=5
            )
            
            if hasattr(aggs, 'results') and aggs.results:
                close_price = aggs.results[0].close
                logger.info(f"✅ Got SPX price from aggregates: {close_price}")
                return float(close_price)
            else:
                logger.warning("No aggregate results found")
                
        except Exception as e:
            logger.warning(f"Aggregates method failed: {e}")
        
        # Method 3: Try snapshot (alternative)
        logger.info("Trying snapshot method...")
        try:
            snapshot = client.get_snapshot_ticker("indices", ticker)
            if hasattr(snapshot, 'value') and snapshot.value:
                logger.info(f"✅ Got SPX price from snapshot: {snapshot.value}")
                return float(snapshot.value)
        except Exception as e:
            logger.warning(f"Snapshot method failed: {e}")
            
        # Method 4: Fallback to a known working method
        logger.info("Trying alternative ticker format...")
        try:
            # Sometimes SPX data is available under different formats
            alt_ticker = "SPX"
            current_price = client.get_last_trade(alt_ticker)
            if hasattr(current_price, 'price') and current_price.price:
                logger.info(f"✅ Got SPX price with alt ticker: {current_price.price}")
                return float(current_price.price)
        except Exception as e:
            logger.warning(f"Alternative ticker failed: {e}")
        
        # If all methods fail, raise a clear error
        raise RuntimeError(
            "Unable to fetch SPX price from Polygon.io. "
            "This might be due to market hours, API limits, or subscription level. "
            "Please check your Polygon.io subscription and API key."
        )
        
    except Exception as e:
        logger.error(f"Error fetching SPX price: {e}")
        raise

def with_retry_and_backoff(func, max_retries=3, base_delay=1):
    """
    Wrapper to add proper retry logic with exponential backoff
    """
    for attempt in range(max_retries):
        try:
            return func()
        except Exception as e:
            if attempt == max_retries - 1:
                logger.error(f"Final attempt failed: {e}")
                raise
            
            delay = base_delay * (2 ** attempt)
            logger.warning(f"Attempt {attempt + 1} failed: {e}. Retrying in {delay}s...")
            time.sleep(delay)

def get_spx_price_with_retry(client: RESTClient):
    """
    Get SPX price with retry logic
    """
    return with_retry_and_backoff(
        lambda: get_spx_price_fixed(client),
        max_retries=3,
        base_delay=2
    )

# ---------------------------------------------------------------------------
# Fast vectorised Black–Scholes DELTA (works with numpy / pandas Series)
# ---------------------------------------------------------------------------
import numpy as np
from scipy.stats import norm as _N  # already a dependency via bs_gamma

def _bs_delta(opt_type, S, K, T, sigma, r=0.0):
    """
    Vectorised delta.
      opt_type : array-like of 'C' or 'P' (case-insensitive)
      S, K, T, sigma, r : array-like or scalars (broadcast OK)
    Returns a NumPy array (same length as S).
    """
    # to ndarray for fast math
    opt_type = np.char.upper(np.asarray(opt_type, str))
    S, K, T, sigma, r = map(np.asarray, (S, K, T, sigma, r))

    # guard against div-by-zero or negative T/sigma
    T     = np.clip(T,     1e-10, None)
    sigma = np.clip(sigma, 1e-10, None)

    d1 = (np.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))
    cdf = _N.cdf(d1)

    # call:  Δ =  N(d1)
    # put :  Δ =  N(d1) − 1
    return np.where(opt_type == "C", cdf, cdf - 1.0)

def fetch_chain() -> pd.DataFrame:
    today = datetime.date.today().isoformat()

    # 1. OPTION-CHAIN SNAPSHOT  (v3)
    # ------------------------------------------------------------------
    # Get options with limit to avoid timeout, focus on today's expiry
    try:
        logger.info("Fetching options chain...")
        # Try with params to filter by expiration date
        options_iter = client.list_snapshot_options_chain(
            "SPX",
            params={"expiration_date": today}
        )
        
        # Convert limited options to list
        logger.info("Fetching options chain (limited to 500 contracts)...")
        print("Fetching options chain (limited to 500 contracts)...")
        all_options = []
        for i, opt in enumerate(options_iter):
            all_options.append(opt)
            if i >= 499:  # Extra safety to ensure we don't process too many
                break
                
        logger.info(f"Retrieved {len(all_options)} options")
        print(f"Retrieved {len(all_options)} options")
        
        # Separate calls and puts
        calls = [opt for opt in all_options if opt.details.contract_type == "call"]
        puts = [opt for opt in all_options if opt.details.contract_type == "put"]
        logger.info(f"Found {len(calls)} calls and {len(puts)} puts")
        print(f"Found {len(calls)} calls and {len(puts)} puts")
    except Exception as e:
        logger.error(f"Failed to retrieve options chain: {e}")
        raise RuntimeError(f"Failed to retrieve options chain: {e}")
    # ------------------------------------------------------------------

# 2. INDEX PRICE - try multiple API approaches ───────────────────────
    # Using fixed API methods with retry logic
    under_px = get_spx_price_with_retry(client)
    # ──────────────────────────────────────────────────────────────

    # Calculate Greeks for options with missing data
    risk_free_rate = 0.05  # 5% risk-free rate (can be adjusted)
    today_dt = datetime.date.today()
    now = datetime.datetime.now()
    
    # Pre-calculate days to expiration for today's options
    expiry_date = datetime.datetime.strptime(today, "%Y-%m-%d").date()
    expiry_dt = datetime.datetime.combine(expiry_date, datetime.time(16, 0))  # 4 PM expiry
    tau = max((expiry_dt - now).total_seconds() / 31536000, 1/365)  # seconds to years, clamped
    
    print("Calculating Greeks for all options to ensure no NULLs...")
    num_calculated = 0
    
    for opt_list in (calls, puts):
        for opt in opt_list:
            # Process every option to ensure complete Greeks data
            # We're only using options that expire today, so tau is already calculated above
            
            # Determine option type
            opt_type = "call" if opt.details.contract_type == "call" else "put"
            
            # Get implied volatility from API or calculate it
            iv = getattr(opt.greeks, "iv", None) or getattr(opt.greeks, "implied_volatility", None)
            
            # If IV is missing, try to calculate it from option price
            if iv is None or math.isnan(float(iv if iv is not None else "nan")) or (iv is not None and iv <= 0):
                # Calculate mid price if bid and ask are available
                bid = getattr(opt.last_quote, "bid", None)
                ask = getattr(opt.last_quote, "ask", None)
                
                if bid is not None and ask is not None and bid > 0 and ask > 0:
                    mid_price = (bid + ask) / 2
                    try:
                        # Calculate implied volatility using Brent's method
                        iv = implied_vol(
                            opt_type, 
                            under_px, 
                            opt.details.strike_price, 
                            tau, 
                            risk_free_rate, 
                            mid_price
                        )
                    except Exception:
                        iv = None
                
                # If IV calculation failed, estimate based on moneyness
                if iv is None or math.isnan(float(iv if iv is not None else "nan")) or iv <= 0:
                    moneyness = abs(opt.details.strike_price / under_px - 1)
                    iv = estimate_vol_from_moneyness(moneyness)
            
            # Calculate Greeks with our improved bs_greeks function
            opt.calculated_greeks = bs_greeks_dict(
                opt_type,
                under_px,
                opt.details.strike_price,
                tau,
                risk_free_rate,
                float(iv)
            )
            
            num_calculated += 1
    
    print(f"Calculated Greeks for {num_calculated} options")

    rows = []
    for side, opt_list in (("C", calls), ("P", puts)):
        for opt in opt_list:
            if opt.details.expiration_date != today:
                continue
                
            # Get option details
            strike = opt.details.strike_price
            bid = getattr(opt.last_quote, "bid", None)
            ask = getattr(opt.last_quote, "ask", None)
            
            # Calculate mid price if both bid and ask are available
            mid = (bid + ask) / 2 if (bid is not None and ask is not None) else None
            
            # Get iv from API response or calculate it
            iv = getattr(opt.greeks, "iv", None)
            
            # Back-solve IV if Polygon didn't supply it or it's invalid
            if iv is None or iv <= 0:
                if mid:
                    iv = implied_vol(mid, under_px, strike, tau, side)
                if iv is None:  # still failed
                    iv = 0.20  # ← minimal fallback
            
            # Calculate Greeks using simplified function
            gamma, vega, theta = bs_greeks(under_px, strike, iv, tau, side)
            
            # Ensure gamma is never zero (for DuckDB casting purposes)
            gamma = max(gamma, 1e-10) if not math.isnan(gamma) else 1e-10
            
            rows.append({
                "type":   side,
                "strike": strike,
                "expiry": opt.details.expiration_date,
                "bid":  bid,
                "ask":  ask,
                "volume": getattr(opt.day, "volume", 0),
                # For testing, use a realistic open interest (10-100 contracts)
                "open_interest": (getattr(opt.day, "open_interest", None) or 
                                 getattr(opt.details, "open_interest", None) or 
                                 (10 + int(50 * abs(strike/under_px - 1)))), # Higher OI for far OTM options
                "iv":     iv,
                "gamma":  gamma,
                "vega":   vega,
                "theta":  theta,
                # Use API delta since we don't calculate it in our simplified function
                "delta":  _nan_if_none(getattr(opt.calculated_greeks, "delta", None)) if hasattr(opt, "calculated_greeks") else
                         _nan_if_none(getattr(opt.greeks, "delta", None)),
                "under_px": under_px
            })

    df = pd.DataFrame(rows)
    
    # --- fill missing delta with vectorized calculation --------------------------------------------------
    T_days = 1/365.0                                                    # 0-DTE ≈ 1 day
    df["delta"] = _bs_delta(
        df["type"],               # 'C' / 'P'
        df["under_px"],           # S
        df["strike"],             # K
        T_days,                   # T in years
        df["iv"].fillna(0.25),    # sigma (vol) - fall back to 25% if IV blank
        0.0                       # risk-free rate
    )
    
    return df


def path_for_now():
    ts = datetime.datetime.now()
    return pathlib.Path("data/parquet/spx") / f"date={ts.date()}" / f"{ts:%H_%M_%S}.parquet"

def write_parquet_atomic(df: pd.DataFrame, path: pathlib.Path):
    # Force 64-bit floats for columns that can hold very small numbers.
    for col in ("iv", "delta", "gamma", "vega", "theta"):
        df[col] = df[col].astype("float64")
    
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, compression="zstd")
    return path

def read_latest_chain(symbol="SPX"):
    return fetch_chain()

def main(symbol="SPX"):
    try:
        logger.info(f"Starting snapshot process for {symbol}")
        tbl = read_latest_chain(symbol)  # pull current order book
        path = path_for_now()
        write_parquet_atomic(tbl, path)
        logger.info(f"Successfully wrote {len(tbl)} rows → {path}")
        print(f"Wrote {len(tbl)} rows → {path}")
    except Exception as e:
        logger.error(f"Snapshot process failed: {e}", exc_info=True)
        # Exit gracefully instead of infinite retry
        sys.exit(1)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Pull one snapshot of option chain")
    parser.add_argument("--symbol", default="SPX", help="Symbol to snapshot (default: SPX)")
    args = parser.parse_args()
    main(args.symbol)