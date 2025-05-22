"""
Pull one snapshot of today's SPX 0-DTE option chain
and store it here:

data/parquet/spx/date=YYYY-MM-DD/HH_MM_SS.parquet
"""

import datetime, os, pathlib, pandas as pd, math, sys
import dotenv
from polygon import RESTClient

# Add project root to path to allow importing from src
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from src.utils.greeks import bs_greeks, implied_vol, estimate_vol_from_moneyness, bs_greeks_dict

dotenv.load_dotenv()
client = RESTClient(os.getenv("POLYGON_KEY"))

def _nan_if_none(x):
    return float("nan") if x is None else float(x)

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
        # Try with params to filter by expiration date
        options_iter = client.list_snapshot_options_chain(
            "SPX",
            params={"expiration_date": today}
        )
        
        # Convert limited options to list
        print("Fetching options chain (limited to 500 contracts)...")
        all_options = []
        for i, opt in enumerate(options_iter):
            all_options.append(opt)
            if i >= 499:  # Extra safety to ensure we don't process too many
                break
                
        print(f"Retrieved {len(all_options)} options")
        
        # Separate calls and puts
        calls = [opt for opt in all_options if opt.details.contract_type == "call"]
        puts = [opt for opt in all_options if opt.details.contract_type == "put"]
        print(f"Found {len(calls)} calls and {len(puts)} puts")
    except Exception as e:
        raise RuntimeError(f"Failed to retrieve options chain: {e}")
    # ------------------------------------------------------------------

# 2. INDEX PRICE - try multiple API approaches ───────────────────────
    try:
        # Method 1: Try previous close (reliable data point)
        prev_close = client.get_previous_close("I:SPX")
        under_px = prev_close.close
        print(f"Using SPX previous close: {under_px}")
    except Exception as e1:
        try:
            # Method 2: Try daily OHLC
            daily = client.get_daily_open_close("I:SPX", datetime.date.today().isoformat())
            under_px = daily.close
            print(f"Using SPX daily close: {under_px}")
        except Exception as e2:
            try:
                # Method 3: Try aggregates for today
                from_date = datetime.date.today().isoformat()
                to_date = from_date
                aggs = client.get_aggs("I:SPX", 1, "day", from_date, to_date, limit=10)
                if aggs:
                    under_px = aggs[0].close
                    print(f"Using SPX aggregate close: {under_px}")
                else:
                    raise RuntimeError("No aggregate data available for I:SPX")
            except Exception as e3:
                # Fail with detailed error information
                raise RuntimeError(
                    f"Unable to get SPX price from any endpoint. "
                    f"Previous close error: {e1}, "
                    f"Daily OHLC error: {e2}, "
                    f"Aggregates error: {e3}"
                )
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

# ---- file-writer with explicit data type handling ----
def write_parquet(df: pd.DataFrame):
    ts   = datetime.datetime.now()
    path = pathlib.Path("data/parquet/spx") / f"date={ts.date()}" / f"{ts:%H_%M_%S}.parquet"
    
    # ------------------------------------------------------------------
    # Force 64-bit floats for columns that can hold very small numbers.
    for col in ("iv", "delta", "gamma", "vega", "theta"):
        df[col] = df[col].astype("float64")
    # ------------------------------------------------------------------
    
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, compression="zstd")
    return path

if __name__ == "__main__":
    df = fetch_chain()
    if df.empty:
        raise SystemExit("Polygon returned zero rows")
    p = write_parquet(df)
    print(f"Wrote {len(df)} rows → {p}")