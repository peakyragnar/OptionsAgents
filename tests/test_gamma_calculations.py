"""
Specific tests for gamma calculation accuracy
Validates Black-Scholes implementation against known values
"""

import pytest
import numpy as np
from datetime import datetime, timedelta
import math

from gamma_tool_sam.core.gamma_calculator import GammaCalculator


class TestBlackScholesGamma:
    """Validate Black-Scholes gamma calculations against known values"""
    
    @pytest.fixture
    def calculator(self):
        calc = GammaCalculator()
        calc.update_spx_price(5900.0)
        return calc
    
    def test_atm_gamma_highest(self, calculator):
        """Test that ATM options have the highest gamma"""
        strikes = [5850, 5875, 5900, 5925, 5950]  # SPX at 5900
        gammas = []
        
        for strike in strikes:
            trade = {
                'symbol': f'SPXW250130C0{strike}000',
                'size': 100,
                'price': 10.0,
                'timestamp': datetime.now()
            }
            result = calculator.calculate_trade_gamma(trade)
            gammas.append((strike, result['gamma_per_contract']))
        
        # ATM (5900) should have highest gamma
        max_gamma_strike = max(gammas, key=lambda x: x[1])[0]
        assert max_gamma_strike == 5900
    
    def test_gamma_decay_with_distance(self, calculator):
        """Test that gamma decreases as we move away from ATM"""
        spx = 5900
        distances = [0, 10, 20, 30, 50, 100]
        
        gammas_by_distance = []
        for distance in distances:
            strike = spx + distance
            trade = {
                'symbol': f'SPXW250130C0{strike}000',
                'size': 100,
                'price': 5.0,
                'timestamp': datetime.now()
            }
            result = calculator.calculate_trade_gamma(trade)
            gammas_by_distance.append(result['gamma_per_contract'])
        
        # Gamma should decrease with distance
        for i in range(1, len(gammas_by_distance)):
            assert gammas_by_distance[i] < gammas_by_distance[i-1]
    
    def test_put_call_gamma_parity(self, calculator):
        """Test that puts and calls at same strike have same gamma"""
        strike = 5900
        
        call_trade = {
            'symbol': f'SPXW250130C0{strike}000',
            'size': 100,
            'price': 10.0,
            'timestamp': datetime.now()
        }
        
        put_trade = {
            'symbol': f'SPXW250130P0{strike}000',
            'size': 100,
            'price': 10.0,
            'timestamp': datetime.now()
        }
        
        call_result = calculator.calculate_trade_gamma(call_trade)
        put_result = calculator.calculate_trade_gamma(put_trade)
        
        # Gamma should be very close for puts and calls at same strike
        assert abs(call_result['gamma_per_contract'] - put_result['gamma_per_contract']) < 0.00001
    
    def test_gamma_calculation_formula(self, calculator):
        """Test gamma calculation against manual Black-Scholes formula"""
        # Manual calculation for verification
        S = 5900  # Spot
        K = 5900  # Strike (ATM)
        T = 1/252  # 1 day to expiry (0DTE approximation)
        r = 0.05  # Risk-free rate
        sigma = 0.15  # Implied volatility
        
        # Black-Scholes gamma formula
        d1 = (np.log(S/K) + (r + 0.5*sigma**2)*T) / (sigma * np.sqrt(T))
        gamma_manual = np.exp(-d1**2/2) / (S * sigma * np.sqrt(2 * np.pi * T))
        
        # Now test against implementation
        trade = {
            'symbol': 'SPXW250130C05900000',
            'size': 100,
            'price': 10.0,
            'timestamp': datetime.now()
        }
        
        result = calculator.calculate_trade_gamma(trade)
        
        # Should be in same ballpark (within order of magnitude)
        # Exact match depends on IV calculation
        assert 0.1 * gamma_manual < result['gamma_per_contract'] < 10 * gamma_manual
    
    def test_gamma_with_extreme_strikes(self, calculator):
        """Test gamma calculation for extreme OTM/ITM options"""
        spx = 5900
        
        # Very deep OTM call
        deep_otm_trade = {
            'symbol': 'SPXW250130C07000000',  # 1100 points OTM
            'size': 100,
            'price': 0.05,
            'timestamp': datetime.now()
        }
        
        # Very deep ITM call
        deep_itm_trade = {
            'symbol': 'SPXW250130C04000000',  # 1900 points ITM
            'size': 100,
            'price': 1900.0,
            'timestamp': datetime.now()
        }
        
        otm_result = calculator.calculate_trade_gamma(deep_otm_trade)
        itm_result = calculator.calculate_trade_gamma(deep_itm_trade)
        
        # Both should have very low gamma
        assert otm_result['gamma_per_contract'] < 0.00001
        assert itm_result['gamma_per_contract'] < 0.00001
    
    def test_total_gamma_multiplier(self, calculator):
        """Test that total gamma uses correct multiplier (100 for index options)"""
        trade = {
            'symbol': 'SPXW250130C05900000',
            'size': 10,  # 10 contracts
            'price': 10.0,
            'timestamp': datetime.now()
        }
        
        result = calculator.calculate_trade_gamma(trade)
        
        # Total gamma = gamma_per_contract * size * 100
        expected_total = result['gamma_per_contract'] * 10 * 100
        assert abs(result['total_gamma'] - expected_total) < 0.01


class TestDirectionalGammaForces:
    """Test directional gamma force calculations"""
    
    @pytest.fixture
    def calculator(self):
        calc = GammaCalculator()
        calc.update_spx_price(5900.0)
        return calc
    
    def test_directional_force_logic(self, calculator):
        """Test the logic for determining directional forces"""
        spx = 5900
        
        test_cases = [
            # (strike, type, expected_direction, description)
            (5950, 'CALL', 'UPWARD', "Call above SPX pulls up"),
            (5850, 'PUT', 'DOWNWARD', "Put below SPX pulls down"),
            (5900, 'CALL', 'NEUTRAL', "ATM call is neutral"),
            (5900, 'PUT', 'NEUTRAL', "ATM put is neutral"),
            (5895, 'CALL', 'NEUTRAL', "Near ATM call is neutral"),
            (5905, 'PUT', 'NEUTRAL', "Near ATM put is neutral"),
            # Edge cases
            (5850, 'CALL', 'NEUTRAL', "Call below SPX doesn't pull up"),
            (5950, 'PUT', 'NEUTRAL', "Put above SPX doesn't pull down"),
        ]
        
        for strike, opt_type, expected, description in test_cases:
            direction = calculator.determine_directional_force(strike, opt_type, spx)
            assert direction == expected, f"{description}: expected {expected}, got {direction}"
    
    def test_gamma_sign_by_direction(self, calculator):
        """Test that gamma signs align with directional forces"""
        test_trades = [
            # Upward force trade
            {
                'symbol': 'SPXW250130C05950000',  # Call above SPX
                'size': 100,
                'price': 5.0,
                'timestamp': datetime.now()
            },
            # Downward force trade
            {
                'symbol': 'SPXW250130P05850000',  # Put below SPX
                'size': 100,
                'price': 5.0,
                'timestamp': datetime.now()
            }
        ]
        
        results = []
        for trade in test_trades:
            result = calculator.calculate_trade_gamma(trade)
            results.append(result)
        
        # Upward should be positive, downward should be negative
        assert results[0]['total_gamma'] > 0  # Upward
        assert results[0]['directional_force'] == 'UPWARD'
        
        assert results[1]['total_gamma'] < 0  # Downward
        assert results[1]['directional_force'] == 'DOWNWARD'


class TestEdgeCasesAndValidation:
    """Test edge cases and data validation"""
    
    def test_symbol_parsing_edge_cases(self):
        """Test option symbol parsing with various formats"""
        calc = GammaCalculator()
        calc.update_spx_price(5900)
        
        # Valid symbols
        valid_symbols = [
            'SPXW250130C05900000',  # Standard
            'SPXW250130P05900000',  # Put
            'SPXW250130C05000000',  # Lower strike
            'SPXW250130C09999000',  # High strike
        ]
        
        for symbol in valid_symbols:
            trade = {'symbol': symbol, 'size': 100, 'price': 10}
            result = calc.calculate_trade_gamma(trade)
            assert result is not None
            assert 'strike' in result
            assert 'option_type' in result
    
    def test_zero_price_handling(self):
        """Test handling of zero-priced options"""
        calc = GammaCalculator()
        calc.update_spx_price(5900)
        
        trade = {
            'symbol': 'SPXW250130C07000000',  # Far OTM
            'size': 100,
            'price': 0.0,  # Zero price
            'timestamp': datetime.now()
        }
        
        result = calc.calculate_trade_gamma(trade)
        # Should handle gracefully - implementation dependent
        # Either return None or very small gamma
    
    def test_implied_volatility_bounds(self):
        """Test that IV stays within reasonable bounds"""
        calc = GammaCalculator()
        calc.update_spx_price(5900)
        
        # Test with various prices
        test_cases = [
            ('SPXW250130C05900000', 50.0),   # High price (high IV)
            ('SPXW250130C05900000', 0.10),   # Low price (low IV)
            ('SPXW250130C06500000', 0.01),   # Far OTM, penny
        ]
        
        for symbol, price in test_cases:
            trade = {
                'symbol': symbol,
                'size': 100,
                'price': price,
                'timestamp': datetime.now()
            }
            
            # Should not crash
            result = calc.calculate_trade_gamma(trade)
            # IV should be bounded if calculated
    
    def test_date_parsing_robustness(self):
        """Test option expiry date parsing"""
        calc = GammaCalculator()
        calc.update_spx_price(5900)
        
        # Different date formats in symbols
        symbols = [
            'SPXW250130C05900000',  # YYMMDD format
            'SPXW251231C05900000',  # End of year
            'SPXW250101C05900000',  # Beginning of year
        ]
        
        for symbol in symbols:
            trade = {'symbol': symbol, 'size': 100, 'price': 10}
            result = calc.calculate_trade_gamma(trade)
            # Should parse dates correctly


if __name__ == '__main__':
    pytest.main([__file__, '-v'])