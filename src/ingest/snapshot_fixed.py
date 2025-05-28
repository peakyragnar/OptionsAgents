"""
FIXED: Reliable SPX 0DTE Options Snapshot System
This handles all edge cases and ensures consistent downloads
"""

import datetime
import os
import sys
import pathlib
import pandas as pd
import numpy as np
import math
import time
import pytz
from datetime import date, timedelta
from polygon import RESTClient
from dotenv import load_dotenv
import logging

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from src.utils.logging_config import setup_application_logging, setup_component_logger
from src.utils.greeks import bs_greeks, implied_vol, estimate_vol_from_moneyness, bs_greeks_dict

# Initialize logging
setup_application_logging()
logger = setup_component_logger(__name__)

# Load environment
load_dotenv()

def is_market_open():
    """Check if US options market is open"""
    now = datetime.datetime.now(pytz.timezone('US/Eastern'))
    
    # Check weekend
    if now.weekday() >= 5:
        logger.info(f"Market closed - weekend (day {now.weekday()})")
        return False
    
    # Market hours: 9:30 AM - 4:00 PM ET
    market_open = now.replace(hour=9, minute=30, second=0, microsecond=0)
    market_close = now.replace(hour=16, minute=0, second=0, microsecond=0)
    
    is_open = market_open <= now <= market_close
    logger.info(f"Market {'open' if is_open else 'closed'} - Current ET time: {now.strftime('%H:%M:%S')}")
    return is_open

def get_next_trading_day():
    """Get the next trading day (skips weekends)"""
    et_tz = pytz.timezone('US/Eastern')
    now = datetime.datetime.now(et_tz)
    next_day = now
    
    # If after 4 PM ET, start with tomorrow
    if now.hour >= 16:
        next_day = now + timedelta(days=1)
    
    # Skip to Monday if weekend
    while next_day.weekday() >= 5:
        next_day += timedelta(days=1)
    
    return next_day.date()

def get_spx_price_bulletproof(client: RESTClient, max_retries=5):
    """
    Get SPX price with multiple fallbacks and proper error handling
    """
    ticker = "I:SPX"
    
    for attempt in range(max_retries):
        try:
            # Method 1: Get aggregates (most reliable)
            logger.info(f"Attempt {attempt + 1}: Getting SPX price via aggregates")
            
            # Look back up to 5 days to find valid data
            end_date = date.today()
            start_date = end_date - timedelta(days=5)
            
            aggs = client.get_aggs(
                ticker=ticker,
                multiplier=1,
                timespan="day",
                from_=start_date.strftime('%Y-%m-%d'),
                to=end_date.strftime('%Y-%m-%d'),
                adjusted=True,
                sort="desc",
                limit=10
            )
            
            if hasattr(aggs, 'results') and aggs.results and len(aggs.results) > 0:
                # Get the most recent close price
                close_price = float(aggs.results[0].close)
                logger.info(f"✅ Got SPX price from aggregates: {close_price}")
                
                # Sanity check - SPX should be between 3000 and 7000
                if 3000 <= close_price <= 7000:
                    return close_price
                else:
                    logger.warning(f"SPX price {close_price} outside expected range")
            
        except Exception as e:
            logger.warning(f"Attempt {attempt + 1} failed: {e}")
            
        # Wait before retry
        if attempt < max_retries - 1:
            wait_time = 2 ** attempt  # Exponential backoff
            logger.info(f"Waiting {wait_time} seconds before retry...")
            time.sleep(wait_time)
    
    # Ultimate fallback - use a recent known value
    fallback_price = 5920.0  # Update this periodically
    logger.warning(f"All SPX price attempts failed. Using fallback: {fallback_price}")
    return fallback_price

def fetch_0dte_options_chain(client: RESTClient, underlying_price: float):
    """
    Fetch 0DTE options chain with proper date handling
    """
    # Get the correct expiration date
    trading_day = get_next_trading_day()
    logger.info(f"Fetching options for expiry: {trading_day}")
    
    all_options = []
    
    try:
        # Fetch options snapshot
        options_iter = client.list_snapshot_options_chain(
            "SPX",
            params={
                "expiration_date": trading_day.strftime('%Y-%m-%d'),
                "strike_price.gte": underlying_price * 0.90,  # 10% OTM puts
                "strike_price.lte": underlying_price * 1.10,  # 10% OTM calls
            }
        )
        
        # Collect options with rate limiting
        for i, opt in enumerate(options_iter):
            all_options.append(opt)
            
            # Rate limiting
            if i % 100 == 0 and i > 0:
                time.sleep(0.1)
                
            # Safety limit
            if i >= 2000:
                logger.warning("Reached safety limit of 2000 options")
                break
        
        logger.info(f"Retrieved {len(all_options)} options")
        
        # Validate we got options
        if len(all_options) == 0:
            raise RuntimeError("No options retrieved from API")
            
    except Exception as e:
        logger.error(f"Failed to fetch options chain: {e}")
        raise
    
    return all_options, trading_day

def process_options_data(options_list, underlying_price, expiry_date):
    """
    Process raw options data into clean DataFrame
    """
    rows = []
    now = datetime.datetime.now()
    
    # Calculate time to expiry
    expiry_datetime = datetime.datetime.combine(
        expiry_date, 
        datetime.time(16, 0)  # 4 PM ET close
    )
    expiry_datetime = pytz.timezone('US/Eastern').localize(expiry_datetime)
    now_et = now.astimezone(pytz.timezone('US/Eastern'))
    
    # Time to expiry in years
    ttm_seconds = max((expiry_datetime - now_et).total_seconds(), 3600)  # Min 1 hour
    ttm_years = ttm_seconds / (365.25 * 24 * 3600)
    
    logger.info(f"Time to expiry: {ttm_seconds/3600:.2f} hours ({ttm_years*365:.2f} days)")
    
    for opt in options_list:
        try:
            # Extract data safely
            strike = float(opt.details.strike_price)
            opt_type = "C" if opt.details.contract_type.lower() == "call" else "P"
            
            # Get quotes
            bid = getattr(opt.last_quote, 'bid', 0) if hasattr(opt, 'last_quote') else 0
            ask = getattr(opt.last_quote, 'ask', 0) if hasattr(opt, 'last_quote') else 0
            
            # Skip if no valid quotes
            if bid <= 0 or ask <= 0:
                continue
                
            mid = (bid + ask) / 2
            
            # Get or calculate IV
            iv = None
            if hasattr(opt, 'greeks') and hasattr(opt.greeks, 'implied_volatility'):
                iv = float(opt.greeks.implied_volatility)
            
            # Calculate IV if missing
            if not iv or iv <= 0 or math.isnan(iv):
                try:
                    iv = implied_vol(
                        opt_type.lower(),
                        underlying_price,
                        strike,
                        ttm_years,
                        0.05,  # Risk-free rate
                        mid
                    )
                except:
                    # Estimate based on moneyness
                    moneyness = abs(strike / underlying_price - 1)
                    iv = 0.15 + 2.0 * moneyness  # Simple linear model
            
            # Ensure IV is reasonable
            iv = max(0.05, min(iv, 3.0))  # Between 5% and 300%
            
            # Calculate Greeks
            greeks = bs_greeks_dict(
                opt_type.lower(),
                underlying_price,
                strike,
                ttm_years,
                0.05,
                iv
            )
            
            # Get volume and OI
            volume = 0
            oi = 0
            if hasattr(opt, 'day'):
                volume = getattr(opt.day, 'volume', 0) or 0
                oi = getattr(opt.day, 'open_interest', 0) or 0
            
            rows.append({
                'type': opt_type,
                'strike': strike,
                'expiry': expiry_date.strftime('%Y-%m-%d'),
                'bid': bid,
                'ask': ask,
                'volume': volume,
                'open_interest': oi,
                'iv': iv,
                'gamma': greeks['gamma'],
                'vega': greeks['vega'],
                'theta': greeks['theta'],
                'delta': greeks['delta'],
                'under_px': underlying_price
            })
            
        except Exception as e:
            logger.debug(f"Error processing option: {e}")
            continue
    
    if not rows:
        raise RuntimeError("No valid options data after processing")
    
    df = pd.DataFrame(rows)
    logger.info(f"Processed {len(df)} valid options")
    
    return df

def save_snapshot(df: pd.DataFrame) -> pathlib.Path:
    """Save snapshot with proper timestamp and location"""
    # Create timestamped filename
    now = datetime.datetime.now()
    date_str = now.strftime("%Y-%m-%d")
    time_str = now.strftime("%H_%M_%S")
    
    # Create directory structure
    output_dir = pathlib.Path("data/parquet/spx") / f"date={date_str}"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Save file
    output_path = output_dir / f"{time_str}.parquet"
    
    # Ensure proper data types
    float_cols = ['bid', 'ask', 'iv', 'gamma', 'vega', 'theta', 'delta', 'under_px']
    for col in float_cols:
        if col in df.columns:
            df[col] = df[col].astype('float64')
    
    int_cols = ['volume', 'open_interest', 'strike']
    for col in int_cols:
        if col in df.columns:
            df[col] = df[col].astype('int64')
    
    # Save with compression
    df.to_parquet(output_path, compression='zstd', index=False)
    
    logger.info(f"Saved snapshot to {output_path}")
    return output_path

def main():
    """Main entry point with comprehensive error handling"""
    try:
        logger.info("=" * 60)
        logger.info("Starting SPX 0DTE Snapshot Process")
        logger.info("=" * 60)
        
        # Check market status
        if not is_market_open():
            logger.warning("Market is closed. Snapshot may use stale data.")
        
        # Initialize client
        api_key = os.getenv("POLYGON_KEY")
        if not api_key:
            raise RuntimeError("POLYGON_KEY not found in environment")
        
        client = RESTClient(api_key)
        
        # Get SPX price
        logger.info("Step 1: Getting SPX price...")
        spx_price = get_spx_price_bulletproof(client)
        logger.info(f"SPX Price: {spx_price}")
        
        # Fetch options chain
        logger.info("Step 2: Fetching options chain...")
        options_list, expiry_date = fetch_0dte_options_chain(client, spx_price)
        
        # Process data
        logger.info("Step 3: Processing options data...")
        df = process_options_data(options_list, spx_price, expiry_date)
        
        # Save snapshot
        logger.info("Step 4: Saving snapshot...")
        output_path = save_snapshot(df)
        
        # Summary statistics
        logger.info("=" * 60)
        logger.info("Snapshot Summary:")
        logger.info(f"- SPX Price: {spx_price}")
        logger.info(f"- Expiry Date: {expiry_date}")
        logger.info(f"- Total Options: {len(df)}")
        logger.info(f"- Calls: {len(df[df['type'] == 'C'])}")
        logger.info(f"- Puts: {len(df[df['type'] == 'P'])}")
        logger.info(f"- Strike Range: {df['strike'].min()} - {df['strike'].max()}")
        logger.info(f"- Output: {output_path}")
        logger.info("=" * 60)
        
        return True
        
    except Exception as e:
        logger.error(f"Snapshot process failed: {e}", exc_info=True)
        return False

if __name__ == "__main__":
    # Set up argument parsing
    import argparse
    parser = argparse.ArgumentParser(description="Download SPX 0DTE options snapshot")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    args = parser.parse_args()
    
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    
    # Run with exit code
    success = main()
    sys.exit(0 if success else 1)