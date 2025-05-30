"""
Gamma Calculator - Calculates directional gamma forces for each trade
Uses Black-Scholes model and determines hedging direction
"""

import numpy as np
from scipy.stats import norm
from typing import Dict, Optional, Tuple
from dataclasses import dataclass
import math

@dataclass
class GammaResult:
    """Results of gamma calculation"""
    strike: int
    option_type: str
    gamma_per_contract: float
    total_gamma: float  # gamma * size
    directional_force: str  # 'UPWARD', 'DOWNWARD', 'NEUTRAL'
    spx_price: float
    
class GammaCalculator:
    """
    Calculates gamma and directional forces for option trades
    
    Key logic:
    - Calls above SPX = Upward force (dealers must buy stock to hedge)
    - Puts below SPX = Downward force (dealers must sell stock to hedge)
    - ATM options = Neutral force
    """
    
    def __init__(self, atm_threshold: float = 10.0):
        self.atm_threshold = atm_threshold
        self.risk_free_rate = 0.05  # 5% risk-free rate
        self.spx_price = None
        
    def update_spx_price(self, price: float):
        """Update current SPX price"""
        self.spx_price = price
        
    def calculate_gamma(self, 
                       strike: float, 
                       spot: float, 
                       time_to_expiry: float,
                       volatility: float) -> float:
        """
        Calculate gamma using Black-Scholes formula
        Gamma is the same for calls and puts
        """
        if time_to_expiry <= 0:
            return 0.0
            
        d1 = (np.log(spot / strike) + (self.risk_free_rate + 0.5 * volatility ** 2) * time_to_expiry) / \
             (volatility * np.sqrt(time_to_expiry))
        
        gamma = norm.pdf(d1) / (spot * volatility * np.sqrt(time_to_expiry))
        
        # SPX multiplier (100 shares per contract)
        return gamma * 100
    
    def determine_directional_force(self, 
                                  strike: int, 
                                  option_type: str, 
                                  spx_price: float) -> str:
        """
        Determine directional force based on strike position
        
        Dealer hedging logic:
        - Short calls above SPX: Must BUY stock if price rises (UPWARD force)
        - Short puts below SPX: Must SELL stock if price falls (DOWNWARD force)
        - ATM options: Can go either way (NEUTRAL)
        """
        distance = abs(strike - spx_price)
        
        # Check if ATM
        if distance <= self.atm_threshold:
            return 'NEUTRAL'
        
        # Calls above SPX create upward pressure
        if option_type == 'CALL' and strike > spx_price:
            return 'UPWARD'
        
        # Puts below SPX create downward pressure
        elif option_type == 'PUT' and strike < spx_price:
            return 'DOWNWARD'
        
        # OTM options on wrong side have minimal effect
        else:
            return 'NEUTRAL'
    
    def calculate_trade_gamma(self, 
                            trade,
                            implied_vol: Optional[float] = None) -> Optional[GammaResult]:
        """
        Calculate gamma for a single trade
        Assumes dealer is SHORT (selling the option)
        """
        if self.spx_price is None:
            return None
            
        # Time to expiry for 0DTE
        now = trade.timestamp
        market_close = now.replace(hour=16, minute=0, second=0)
        hours_to_expiry = max(0, (market_close - now).total_seconds() / 3600)
        time_to_expiry = hours_to_expiry / (252 * 6.5)  # Convert to years
        
        # Use provided IV or estimate based on moneyness
        if implied_vol is None:
            moneyness = trade.strike / self.spx_price
            # Simple IV smile - higher IV for OTM options
            base_iv = 0.15  # 15% base volatility
            smile_adjustment = 0.05 * abs(1 - moneyness)
            implied_vol = base_iv + smile_adjustment
        
        # Calculate gamma
        gamma_per_contract = self.calculate_gamma(
            strike=trade.strike,
            spot=self.spx_price,
            time_to_expiry=time_to_expiry,
            volatility=implied_vol
        )
        
        # Total gamma (negative because dealers are SHORT)
        total_gamma = -gamma_per_contract * trade.size
        
        # Determine directional force
        direction = self.determine_directional_force(
            strike=trade.strike,
            option_type=trade.option_type,
            spx_price=self.spx_price
        )
        
        return GammaResult(
            strike=trade.strike,
            option_type=trade.option_type,
            gamma_per_contract=gamma_per_contract,
            total_gamma=total_gamma,
            directional_force=direction,
            spx_price=self.spx_price
        )
    
    def calculate_net_directional_force(self, gamma_results: list) -> Dict:
        """
        Calculate net directional market force from all positions
        """
        upward_force = sum(abs(g.total_gamma) for g in gamma_results 
                          if g.directional_force == 'UPWARD')
        downward_force = sum(abs(g.total_gamma) for g in gamma_results 
                            if g.directional_force == 'DOWNWARD')
        neutral_force = sum(abs(g.total_gamma) for g in gamma_results 
                           if g.directional_force == 'NEUTRAL')
        
        net_force = upward_force - downward_force
        
        return {
            'net_force': net_force,
            'upward_force': upward_force,
            'downward_force': downward_force,
            'neutral_force': neutral_force,
            'expected_direction': 'UP' if net_force > 0 else 'DOWN',
            'confidence': min(abs(net_force) / 1000000, 1.0)  # Normalize
        }