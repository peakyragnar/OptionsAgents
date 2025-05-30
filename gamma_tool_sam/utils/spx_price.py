"""
SPX Price Fetcher for Gamma Tool Sam
Gets real-time SPX price from Polygon API
"""

import os
import asyncio
from datetime import datetime, timedelta
from typing import Optional, Tuple
import logging

from polygon import RESTClient
from polygon.rest.models import Agg

logger = logging.getLogger(__name__)


class SPXPriceFetcher:
    """Fetches SPX price from Polygon with caching"""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv('POLYGON_KEY')
        if not self.api_key:
            raise ValueError("POLYGON_KEY environment variable not set")
            
        self.client = RESTClient(self.api_key)
        self._cache = {}
        self._cache_duration = 10  # seconds
        
    def get_spy_price(self) -> Optional[float]:
        """Get SPY price as fallback (multiply by 10 for SPX estimate)"""
        cache_key = 'spy_live'
        if cache_key in self._cache:
            price, timestamp = self._cache[cache_key]
            if (datetime.now() - timestamp).total_seconds() < self._cache_duration:
                return price
                
        try:
            now = datetime.now()
            today = now.strftime('%Y-%m-%d')
            
            # Get SPY minute bars
            aggs = self.client.get_aggs(
                ticker="SPY",
                multiplier=1,
                timespan="minute",
                from_=today,
                to=today,
                adjusted=True,
                sort="desc",
                limit=1
            )
            
            results = list(aggs)
            if results:
                price = float(results[0].close)
                if 300 <= price <= 700:  # SPY range
                    self._cache[cache_key] = (price, datetime.now())
                    logger.info(f"Got SPY price: ${price:,.2f}")
                    return price
                    
        except Exception as e:
            logger.debug(f"Failed to get SPY price: {e}")
            
        return None
        
    def get_live_spx_price(self) -> Optional[float]:
        """Get live SPX price from Polygon"""
        # Check cache first
        cache_key = 'spx_live'
        if cache_key in self._cache:
            price, timestamp = self._cache[cache_key]
            if (datetime.now() - timestamp).total_seconds() < self._cache_duration:
                return price
                
        try:
            # During market hours, get minute bars
            now = datetime.now()
            today = now.strftime('%Y-%m-%d')
            
            # Try different ticker symbols for SPX
            for ticker in ["I:SPX", "SPX", "SPY"]:
                try:
                    # Get last few minute bars
                    aggs = self.client.get_aggs(
                        ticker=ticker,
                        multiplier=1,
                        timespan="minute",
                        from_=today,
                        to=today,
                        adjusted=True,
                        sort="desc",
                        limit=5
                    )
                    
                    results = list(aggs)
                    if results:
                        latest = results[0]
                        price = float(latest.close)
                        
                        # SPY needs to be multiplied by 10 to approximate SPX
                        if ticker == "SPY":
                            price = price * 10
                            
                        # Sanity check
                        if 3000 <= price <= 7000:
                            # Cache the result
                            self._cache[cache_key] = (price, datetime.now())
                            logger.info(f"Got live {ticker} price: ${price:,.2f}")
                            return price
                        else:
                            logger.warning(f"{ticker} price {price} outside expected range")
                            
                except Exception as e:
                    logger.debug(f"Failed to get {ticker} minute bars: {e}")
                    continue
            
            # If we get here, all ticker attempts failed
            logger.warning("Could not get minute bars for any SPX ticker")
                    
        except Exception as e:
            logger.error(f"Failed to get live SPX price: {e}")
            
        # Fallback to previous close
        return self.get_previous_close()
        
    def get_previous_close(self) -> Optional[float]:
        """Get previous close price for SPX"""
        cache_key = 'spx_close'
        if cache_key in self._cache:
            price, timestamp = self._cache[cache_key]
            if (datetime.now() - timestamp).total_seconds() < 300:  # 5 min cache
                return price
                
        try:
            # Try different methods to get previous close
            for ticker in ["I:SPX", "SPX", "SPY"]:
                try:
                    # Get previous day aggregate
                    yesterday = (datetime.now() - timedelta(days=1)).strftime('%Y-%m-%d')
                    aggs = self.client.get_aggs(
                        ticker=ticker,
                        multiplier=1,
                        timespan="day",
                        from_=yesterday,
                        to=yesterday,
                        adjusted=True,
                        limit=1
                    )
                    
                    results = list(aggs)
                    if results:
                        price = float(results[0].close)
                        
                        # SPY adjustment
                        if ticker == "SPY":
                            price = price * 10
                            
                        if 3000 <= price <= 7000:
                            self._cache[cache_key] = (price, datetime.now())
                            logger.info(f"Got {ticker} previous close: ${price:,.2f}")
                            return price
                            
                except Exception as e:
                    logger.debug(f"Failed to get {ticker} previous close: {e}")
                    continue
                    
        except Exception as e:
            logger.error(f"Failed to get SPX previous close: {e}")
            
        return None
        
    def get_quote(self) -> Optional[Tuple[float, float]]:
        """Get SPX quote from various sources"""
        # Try quote cache first
        try:
            from src.stream.quote_cache import quotes
            
            # Check various possible SPX symbols
            for symbol in ['I:SPX', 'SPX', '$SPX']:
                quote = quotes.get(symbol)
                if quote:
                    bid = quote.get('bid', 0)
                    ask = quote.get('ask', 0)
                    if bid > 0 and ask > 0 and 3000 <= bid <= 7000:
                        logger.info(f"Got {symbol} quote from cache: ${bid:,.2f} / ${ask:,.2f}")
                        return (bid, ask)
                        
        except Exception as e:
            logger.debug(f"Quote cache not available: {e}")
            
        return None


# Global instance
_fetcher = None

def get_spx_price() -> float:
    """Get current SPX price with fallback logic"""
    global _fetcher
    
    if _fetcher is None:
        _fetcher = SPXPriceFetcher()
        
    # Try multiple methods
    price = _fetcher.get_live_spx_price()
    if price:
        return price
        
    # Try quote
    quote = _fetcher.get_quote()
    if quote:
        return (quote[0] + quote[1]) / 2
        
    # Try previous close
    price = _fetcher.get_previous_close()
    if price:
        return price
        
    # Try SPY as last resort
    try:
        spy_price = _fetcher.get_spy_price()
        if spy_price:
            spx_estimate = spy_price * 10
            logger.warning(f"Using SPY-based estimate: ${spx_estimate:,.2f}")
            return spx_estimate
    except:
        pass
        
    # Ultimate fallback
    logger.warning("Using fallback SPX price")
    return 5920.0  # Update this as needed


async def update_spx_price_loop(engine, interval: int = 10):
    """Async loop to update SPX price in engine"""
    while True:
        try:
            price = get_spx_price()
            engine.update_spx_price(price)
            await asyncio.sleep(interval)
        except Exception as e:
            logger.error(f"Error updating SPX price: {e}")
            await asyncio.sleep(interval)