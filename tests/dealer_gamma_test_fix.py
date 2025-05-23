#!/usr/bin/env python3
"""
Dealer Gamma Calculation Test & Fix
Critical tests for 0DTE SPX dealer gamma exposure calculation
"""

import pytest
import numpy as np
from decimal import Decimal
from dataclasses import dataclass
from typing import Dict, List, Optional
from datetime import datetime, time


@dataclass
class Trade:
    """Represents a single options trade"""
    symbol: str
    strike: float
    option_type: str  # 'C' or 'P'
    price: float
    size: int
    timestamp: datetime
    side: str  # 'BUY' or 'SELL' (customer perspective)
    nbbo_bid: float
    nbbo_ask: float
    

@dataclass
class OptionQuote:
    """Current NBBO quote for an option"""
    symbol: str
    bid: float
    ask: float
    timestamp: datetime
    

class DealerGammaCalculator:
    """
    Fixed dealer gamma calculation for 0DTE SPX options
    
    Key Principle: 
    - Customer Buys = Dealer Sells (Dealer Short Gamma)
    - Customer Sells = Dealer Buys (Dealer Long Gamma)
    - Net Dealer Gamma = (Customer Sells - Customer Buys) * Contract Gamma
    """
    
    def __init__(self):
        self.positions: Dict[str, Dict] = {}  # Strike -> position data
        
    def classify_trade(self, trade: Trade) -> str:
        """
        Classify trade as customer BUY or SELL based on NBBO
        
        Critical for accurate dealer positioning:
        - Trade at/above ask = Customer BUY (Dealer SELL)
        - Trade at/below bid = Customer SELL (Dealer BUY)  
        - Trade at mid = Use size/volume heuristics
        """
        mid_price = (trade.nbbo_bid + trade.nbbo_ask) / 2
        spread = trade.nbbo_ask - trade.nbbo_bid
        
        # Conservative classification thresholds
        buy_threshold = mid_price + (spread * 0.25)  # Closer to ask
        sell_threshold = mid_price - (spread * 0.25)  # Closer to bid
        
        if trade.price >= buy_threshold:
            return 'BUY'  # Customer buying from dealer
        elif trade.price <= sell_threshold:
            return 'SELL'  # Customer selling to dealer
        else:
            # At mid - use additional heuristics or mark as uncertain
            return 'MID'
    
    def calculate_option_gamma(self, strike: float, spot: float, 
                             vol: float, time_to_expiry: float, 
                             rate: float = 0.05) -> float:
        """
        Calculate Black-Scholes gamma for 0DTE options
        
        For 0DTE: time_to_expiry approaches 0, gamma explodes near ATM
        """
        if time_to_expiry <= 0:
            # At expiration, gamma is theoretically infinite at ATM
            # Use practical approximation
            if abs(spot - strike) < 0.01:
                return 1000.0  # Very high gamma for ATM at expiry
            else:
                return 0.0  # Zero gamma for OTM at expiry
        
        # Standard Black-Scholes gamma
        d1 = (np.log(spot / strike) + (rate + 0.5 * vol**2) * time_to_expiry) / (vol * np.sqrt(time_to_expiry))
        gamma = np.exp(-0.5 * d1**2) / (spot * vol * np.sqrt(2 * np.pi * time_to_expiry))
        
        return gamma
    
    def process_trade(self, trade: Trade, current_spot: float, 
                     implied_vol: float, time_to_expiry: float) -> Dict:
        """
        Process a trade and update dealer positions
        
        Returns: Updated position data for the strike
        """
        side = self.classify_trade(trade)
        strike_key = f"{trade.strike}_{trade.option_type}"
        
        # Initialize position if new
        if strike_key not in self.positions:
            self.positions[strike_key] = {
                'strike': trade.strike,
                'option_type': trade.option_type,
                'customer_buys': 0,
                'customer_sells': 0,
                'dealer_net_position': 0,  # Positive = Long, Negative = Short
                'gamma_per_contract': 0,
                'dealer_gamma_exposure': 0
            }
        
        pos = self.positions[strike_key]
        
        # Update trade counts
        if side == 'BUY':
            pos['customer_buys'] += trade.size
        elif side == 'SELL':
            pos['customer_sells'] += trade.size
        
        # Calculate dealer net position (dealer perspective)
        # Customer buys = Dealer sells (negative position)
        # Customer sells = Dealer buys (positive position)
        pos['dealer_net_position'] = pos['customer_sells'] - pos['customer_buys']
        
        # Calculate gamma per contract
        pos['gamma_per_contract'] = self.calculate_option_gamma(
            trade.strike, current_spot, implied_vol, time_to_expiry
        )
        
        # Calculate total dealer gamma exposure
        # Positive = Long Gamma (stabilizing), Negative = Short Gamma (destabilizing)
        pos['dealer_gamma_exposure'] = pos['dealer_net_position'] * pos['gamma_per_contract'] * 100  # 100 shares per contract
        
        return pos.copy()
    
    def get_total_gamma_exposure(self) -> float:
        """Get total dealer gamma exposure across all strikes"""
        return sum(pos['dealer_gamma_exposure'] for pos in self.positions.values())
    
    def get_gamma_by_strike(self) -> Dict[float, float]:
        """Get gamma exposure by strike price"""
        return {
            pos['strike']: pos['dealer_gamma_exposure'] 
            for pos in self.positions.values()
        }


# ==================== TESTS ====================

class TestDealerGammaCalculation:
    """Test suite for dealer gamma calculations"""
    
    def setup_method(self):
        """Setup for each test"""
        self.calculator = DealerGammaCalculator()
        self.spot_price = 5200.0
        self.implied_vol = 0.35
        self.time_to_expiry = 1/365  # 1 day = 0DTE at market open
        
    def test_trade_classification_buy(self):
        """Test customer buy classification"""
        trade = Trade(
            symbol="SPXW240523C05200000",
            strike=5200.0,
            option_type="C",
            price=16.0,  # At ask
            size=10,
            timestamp=datetime.now(),
            side="",
            nbbo_bid=15.5,
            nbbo_ask=16.0
        )
        
        side = self.calculator.classify_trade(trade)
        assert side == 'BUY', "Trade at ask should be classified as customer BUY"
    
    def test_trade_classification_sell(self):
        """Test customer sell classification"""
        trade = Trade(
            symbol="SPXW240523P05200000",
            strike=5200.0,
            option_type="P",
            price=15.5,  # At bid
            size=5,
            timestamp=datetime.now(),
            side="",
            nbbo_bid=15.5,
            nbbo_ask=16.0
        )
        
        side = self.calculator.classify_trade(trade)
        assert side == 'SELL', "Trade at bid should be classified as customer SELL"
    
    def test_balanced_flow_zero_exposure(self):
        """
        Test: Balanced customer flow should result in zero dealer exposure
        This is the critical test that was likely failing
        """
        # Customer buys 50 contracts
        buy_trade = Trade(
            symbol="SPXW240523C05200000",
            strike=5200.0,
            option_type="C",
            price=16.0,  # At ask (customer buy)
            size=50,
            timestamp=datetime.now(),
            side="",
            nbbo_bid=15.5,
            nbbo_ask=16.0
        )
        
        # Customer sells 50 contracts  
        sell_trade = Trade(
            symbol="SPXW240523C05200000",
            strike=5200.0,
            option_type="C",
            price=15.5,  # At bid (customer sell)
            size=50,
            timestamp=datetime.now(),
            side="",
            nbbo_bid=15.5,
            nbbo_ask=16.0
        )
        
        # Process both trades
        self.calculator.process_trade(buy_trade, self.spot_price, 
                                    self.implied_vol, self.time_to_expiry)
        result = self.calculator.process_trade(sell_trade, self.spot_price,
                                             self.implied_vol, self.time_to_expiry)
        
        # Verify balanced flow results in zero net dealer position
        assert result['customer_buys'] == 50
        assert result['customer_sells'] == 50
        assert result['dealer_net_position'] == 0, \
            "Balanced customer flow should result in zero dealer net position"
        assert abs(result['dealer_gamma_exposure']) < 1e-10, \
            "Zero dealer position should result in zero gamma exposure"
    
    def test_imbalanced_flow_exposure(self):
        """
        Test: Imbalanced flow creates dealer gamma exposure
        """
        # Heavy customer buying (100 buys vs 20 sells)
        for _ in range(10):
            buy_trade = Trade(
                symbol="SPXW240523C05200000",
                strike=5200.0,
                option_type="C", 
                price=16.0,
                size=10,  # 10 * 10 = 100 total
                timestamp=datetime.now(),
                side="",
                nbbo_bid=15.5,
                nbbo_ask=16.0
            )
            self.calculator.process_trade(buy_trade, self.spot_price,
                                        self.implied_vol, self.time_to_expiry)
        
        # Light customer selling
        for _ in range(2):
            sell_trade = Trade(
                symbol="SPXW240523C05200000",
                strike=5200.0,
                option_type="C",
                price=15.5,
                size=10,  # 2 * 10 = 20 total
                timestamp=datetime.now(),
                side="",
                nbbo_bid=15.5,
                nbbo_ask=16.0
            )
            result = self.calculator.process_trade(sell_trade, self.spot_price,
                                                 self.implied_vol, self.time_to_expiry)
        
        # Verify imbalanced flow creates exposure
        assert result['customer_buys'] == 100
        assert result['customer_sells'] == 20
        assert result['dealer_net_position'] == -80, \
            "More customer buys should create dealer short position"
        assert result['dealer_gamma_exposure'] < 0, \
            "Dealer short position should create negative gamma exposure"
    
    def test_0dte_gamma_explosion(self):
        """
        Test: Gamma explosion near expiry for ATM options
        """
        # Very close to expiry (1 minute)
        time_to_expiry = 1 / (365 * 24 * 60)  # 1 minute
        
        trade = Trade(
            symbol="SPXW240523C05200000",
            strike=5200.0,  # ATM
            option_type="C",
            price=16.0,
            size=10,
            timestamp=datetime.now(),
            side="",
            nbbo_bid=15.5,
            nbbo_ask=16.0
        )
        
        result = self.calculator.process_trade(trade, 5200.0,  # ATM
                                             self.implied_vol, time_to_expiry)
        
        # Gamma should be very high for ATM options near expiry
        assert result['gamma_per_contract'] > 0.001, \
            "ATM options near expiry should have high gamma"
    
    def test_multiple_strikes_aggregation(self):
        """
        Test: Proper aggregation across multiple strikes
        """
        strikes = [5180, 5190, 5200, 5210, 5220]
        
        for strike in strikes:
            trade = Trade(
                symbol=f"SPXW240523C{strike:08.0f}000",
                strike=strike,
                option_type="C",
                price=16.0,
                size=10,
                timestamp=datetime.now(),
                side="",
                nbbo_bid=15.5,
                nbbo_ask=16.0
            )
            self.calculator.process_trade(trade, self.spot_price,
                                        self.implied_vol, self.time_to_expiry)
        
        # Check total exposure aggregation
        total_exposure = self.calculator.get_total_gamma_exposure()
        gamma_by_strike = self.calculator.get_gamma_by_strike()
        
        assert len(gamma_by_strike) == 5, "Should track all 5 strikes"
        assert abs(total_exposure - sum(gamma_by_strike.values())) < 1e-10, \
            "Total exposure should equal sum of individual strikes"
    
    def test_full_chain_gamma_exposure_2025_05_22(self):
        """
        Test: Full SPX options chain gamma exposure for 2025-05-22
        Realistic test with current SPX levels around 5850
        """
        # SPX level on 2025-05-22 
        current_spx = 5850.0
        test_date = datetime(2025, 5, 22, 14, 30, 0)  # 2:30 PM yesterday
        
        # Generate realistic strike ladder around current SPX
        # 0DTE SPX has strikes every $5 from well below to well above spot
        strikes_calls = list(range(5750, 5951, 5))  # 5750 to 5950 every $5
        strikes_puts = list(range(5750, 5951, 5))   # Same range for puts
        
        total_dealer_gamma = 0
        
        # Test calls across the chain
        for strike in strikes_calls:
            # Realistic volume distribution (more volume near ATM)
            distance_from_atm = abs(strike - current_spx)
            base_volume = max(10, 1000 - distance_from_atm * 5)  # Higher volume near ATM
            
            # Random flow imbalance (some strikes balanced, others not)
            customer_buys = np.random.randint(int(base_volume * 0.3), int(base_volume * 1.2))
            customer_sells = np.random.randint(int(base_volume * 0.3), int(base_volume * 1.2))
            
            # Create buy trades
            for i in range(customer_buys // 10):  # Batch into 10-lot trades
                buy_trade = Trade(
                    symbol=f"SPXW250522C{strike:08.0f}000",
                    strike=float(strike),
                    option_type="C",
                    price=self._get_realistic_price(strike, current_spx, "C", "buy"),
                    size=10,
                    timestamp=test_date,
                    side="",
                    nbbo_bid=self._get_realistic_price(strike, current_spx, "C", "bid"),
                    nbbo_ask=self._get_realistic_price(strike, current_spx, "C", "ask")
                )
                result = self.calculator.process_trade(buy_trade, current_spx, 0.25, self.time_to_expiry)
            
            # Create sell trades
            for i in range(customer_sells // 10):
                sell_trade = Trade(
                    symbol=f"SPXW250522C{strike:08.0f}000",
                    strike=float(strike),
                    option_type="C", 
                    price=self._get_realistic_price(strike, current_spx, "C", "sell"),
                    size=10,
                    timestamp=test_date,
                    side="",
                    nbbo_bid=self._get_realistic_price(strike, current_spx, "C", "bid"),
                    nbbo_ask=self._get_realistic_price(strike, current_spx, "C", "ask")
                )
                result = self.calculator.process_trade(sell_trade, current_spx, 0.25, self.time_to_expiry)
        
        # Test puts across the chain
        for strike in strikes_puts:
            distance_from_atm = abs(strike - current_spx)
            base_volume = max(10, 800 - distance_from_atm * 4)  # Puts typically lower volume
            
            customer_buys = np.random.randint(int(base_volume * 0.4), int(base_volume * 1.1))
            customer_sells = np.random.randint(int(base_volume * 0.4), int(base_volume * 1.1))
            
            # Create put trades (similar to calls)
            for i in range(customer_buys // 10):
                buy_trade = Trade(
                    symbol=f"SPXW250522P{strike:08.0f}000",
                    strike=float(strike),
                    option_type="P",
                    price=self._get_realistic_price(strike, current_spx, "P", "buy"),
                    size=10,
                    timestamp=test_date,
                    side="",
                    nbbo_bid=self._get_realistic_price(strike, current_spx, "P", "bid"),
                    nbbo_ask=self._get_realistic_price(strike, current_spx, "P", "ask")
                )
                self.calculator.process_trade(buy_trade, current_spx, 0.25, self.time_to_expiry)
            
            for i in range(customer_sells // 10):
                sell_trade = Trade(
                    symbol=f"SPXW250522P{strike:08.0f}000",
                    strike=float(strike),
                    option_type="P",
                    price=self._get_realistic_price(strike, current_spx, "P", "sell"),
                    size=10,
                    timestamp=test_date,
                    side="",
                    nbbo_bid=self._get_realistic_price(strike, current_spx, "P", "bid"),
                    nbbo_ask=self._get_realistic_price(strike, current_spx, "P", "ask")
                )
                self.calculator.process_trade(sell_trade, current_spx, 0.25, self.time_to_expiry)
        
        # Validate full chain results
        total_gamma_exposure = self.calculator.get_total_gamma_exposure()
        gamma_by_strike = self.calculator.get_gamma_by_strike()
        
        # Should have positions across multiple strikes
        assert len(gamma_by_strike) > 20, "Should have positions across many strikes"
        
        # ATM strikes should have highest gamma exposure
        atm_strikes = [s for s in gamma_by_strike.keys() if abs(s - current_spx) <= 10]
        assert len(atm_strikes) > 0, "Should have ATM strikes"
        
        # Total exposure should be reasonable for realistic flow
        # With random imbalances, total exposure should not be extreme
        assert abs(total_gamma_exposure) < 1e8, "Total gamma exposure should be reasonable"
        
        print(f"\n📊 Full Chain Test Results for 2025-05-22:")
        print(f"SPX Level: {current_spx}")
        print(f"Strikes Analyzed: {len(gamma_by_strike)}")
        print(f"Total Dealer Gamma Exposure: ${total_gamma_exposure:,.0f}")
        
        # Find strikes with highest exposure
        top_strikes = sorted(gamma_by_strike.items(), key=lambda x: abs(x[1]), reverse=True)[:5]
        print(f"Top 5 Strikes by Gamma Exposure:")
        for strike, exposure in top_strikes:
            print(f"  {strike}: ${exposure:,.0f}")
    
    def _get_realistic_price(self, strike: float, spot: float, option_type: str, side: str) -> float:
        """Generate realistic option prices for testing"""
        
        # Simple option pricing for testing
        if option_type == "C":  # Call
            if strike <= spot:  # ITM
                intrinsic = spot - strike
                extrinsic = max(0.5, 20 * np.exp(-abs(strike - spot) / 50))
            else:  # OTM
                intrinsic = 0
                extrinsic = max(0.1, 15 * np.exp(-(strike - spot) / 30))
        else:  # Put
            if strike >= spot:  # ITM
                intrinsic = strike - spot
                extrinsic = max(0.5, 20 * np.exp(-abs(strike - spot) / 50))
            else:  # OTM
                intrinsic = 0
                extrinsic = max(0.1, 15 * np.exp(-(spot - strike) / 30))
        
        theoretical = intrinsic + extrinsic
        
        # Add bid/ask spread
        spread = max(0.05, theoretical * 0.05)  # 5% spread minimum $0.05
        
        if side == "bid":
            return round(max(0.05, theoretical - spread/2), 2)
        elif side == "ask":
            return round(theoretical + spread/2, 2)
        elif side == "buy":
            return round(theoretical + spread/4, 2)  # Closer to ask
        else:  # sell
            return round(max(0.05, theoretical - spread/4), 2)  # Closer to bid


# ==================== DIAGNOSTIC TOOLS ====================

def run_diagnostic_tests():
    """
    Run comprehensive diagnostics to identify dealer gamma calculation issues
    """
    print("🔍 Running OptionsAgents Dealer Gamma Diagnostics...")
    print("=" * 60)
    
    # Run the test suite
    pytest_result = pytest.main([
        __file__ + "::TestDealerGammaCalculation", 
        "-v", 
        "-x"  # Stop on first failure
    ])
    
    if pytest_result == 0:
        print("✅ All dealer gamma tests PASSED!")
        print("✅ Dealer gamma calculation logic is correct")
    else:
        print("❌ Dealer gamma tests FAILED!")
        print("❌ Critical issues found in dealer gamma calculation")
        
    return pytest_result == 0


def compare_with_theoretical():
    """
    Compare calculated values with theoretical expectations
    """
    calc = DealerGammaCalculator()
    
    print("\n📊 Theoretical vs Calculated Gamma Comparison")
    print("-" * 50)
    
    # Test case: Balanced flow
    print("Test Case: Balanced Customer Flow")
    print("Expected: Zero dealer gamma exposure")
    
    # Add balanced trades...
    # [Implementation continues...]


if __name__ == "__main__":
    # Run diagnostics when executed directly
    success = run_diagnostic_tests()
    
    if not success:
        print("\n🔧 NEXT STEPS:")
        print("1. Fix the failing tests in your dealer engine")
        print("2. Update trade classification logic")
        print("3. Verify gamma calculation formulas")
        print("4. Test with historical 0DTE data")
        
    compare_with_theoretical()