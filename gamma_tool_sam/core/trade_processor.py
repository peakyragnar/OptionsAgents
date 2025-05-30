"""
Trade Processor - Receives and processes all SPX 0DTE option trades
No filtering - all trades are meaningful including penny trades
"""

import re
from datetime import datetime
from typing import Dict, Optional, Tuple
from dataclasses import dataclass
import asyncio
from collections import defaultdict

@dataclass
class OptionTrade:
    """Structured option trade data"""
    timestamp: datetime
    symbol: str
    strike: int
    option_type: str  # 'CALL' or 'PUT'
    price: float
    size: int
    conditions: list
    exchange: str

class TradeProcessor:
    """
    Processes incoming SPX 0DTE option trades
    Assumes all volume represents institutional selling
    """
    
    def __init__(self):
        self.trades_processed = 0
        self.strike_pattern = re.compile(r'O:SPXW?\d{6}([CP])(\d{8})')
        self.current_trades = []
        self.callbacks = []
        
    def parse_option_symbol(self, symbol: str) -> Optional[Tuple[str, int]]:
        """
        Parse option symbol to extract type and strike
        Example: O:SPXW250530C05910000 -> ('CALL', 5910)
        """
        match = self.strike_pattern.match(symbol)
        if not match:
            return None
            
        option_type = 'CALL' if match.group(1) == 'C' else 'PUT'
        strike = int(match.group(2)) // 1000  # Convert from 05910000 to 5910
        
        return option_type, strike
    
    def process_trade(self, trade_data: Dict) -> Optional[OptionTrade]:
        """
        Process raw trade data into structured format
        All trades processed - no filtering
        """
        symbol = trade_data.get('symbol', '')
        
        # Parse option details
        parsed = self.parse_option_symbol(symbol)
        if not parsed:
            return None
            
        option_type, strike = parsed
        
        # Check if 0DTE (compare dates)
        if not self._is_zero_dte(symbol):
            return None
        
        # Create structured trade
        trade = OptionTrade(
            timestamp=datetime.fromtimestamp(trade_data['timestamp'] / 1000),
            symbol=symbol,
            strike=strike,
            option_type=option_type,
            price=trade_data['price'],
            size=trade_data['size'],
            conditions=trade_data.get('conditions', []),
            exchange=trade_data.get('exchange', '')
        )
        
        self.trades_processed += 1
        self.current_trades.append(trade)
        
        # Notify callbacks
        for callback in self.callbacks:
            callback(trade)
            
        return trade
    
    def _is_zero_dte(self, symbol: str) -> bool:
        """Check if option expires today"""
        # Extract date from symbol (YYMMDD format)
        try:
            # O:SPXW250530C05910000
            date_part = symbol[6:12]  # 250530
            year = 2000 + int(date_part[:2])
            month = int(date_part[2:4])
            day = int(date_part[4:6])
            
            expiry = datetime(year, month, day).date()
            today = datetime.now().date()
            
            return expiry == today
        except:
            return False
    
    def register_callback(self, callback):
        """Register callback for processed trades"""
        self.callbacks.append(callback)
    
    def get_recent_trades(self, seconds: int = 60) -> list:
        """Get trades from last N seconds"""
        cutoff = datetime.now().timestamp() - seconds
        return [t for t in self.current_trades 
                if t.timestamp.timestamp() > cutoff]
    
    def get_stats(self) -> Dict:
        """Get processing statistics"""
        return {
            'trades_processed': self.trades_processed,
            'current_buffer_size': len(self.current_trades),
            'strikes_active': len(set(t.strike for t in self.current_trades))
        }