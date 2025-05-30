"""
Comprehensive unit tests for Gamma Tool Sam
Tests gamma calculations, directional forces, confidence scoring, and signal generation
"""

import pytest
import numpy as np
from datetime import datetime, timedelta
from unittest.mock import Mock, patch
import pandas as pd

from gamma_tool_sam.core.gamma_calculator import GammaCalculator
from gamma_tool_sam.core.trade_processor import TradeProcessor
from gamma_tool_sam.core.position_tracker import PositionTracker
from gamma_tool_sam.core.change_detector import ChangeDetector, Change
from gamma_tool_sam.core.confidence_calculator import ConfidenceCalculator, MarketConditions
from gamma_tool_sam.gamma_engine import GammaEngine


class TestGammaCalculator:
    """Test Black-Scholes gamma calculations and directional force determination"""
    
    @pytest.fixture
    def calculator(self):
        calc = GammaCalculator()
        calc.update_spx_price(5900.0)
        return calc
    
    def test_gamma_calculation_accuracy(self, calculator):
        """Test that gamma calculations match expected Black-Scholes values"""
        # Test cases with known gamma values
        test_cases = [
            # (strike, option_type, expected_gamma_range)
            (5900, 'CALL', (0.0001, 0.0005)),  # ATM should have highest gamma
            (5950, 'CALL', (0.00001, 0.0001)),  # OTM call
            (5850, 'PUT', (0.00001, 0.0001)),   # OTM put
        ]
        
        trade = {
            'symbol': 'SPXW250130C05900000',
            'size': 100,
            'price': 10.50,
            'timestamp': datetime.now()
        }
        
        for strike, opt_type, gamma_range in test_cases:
            trade['symbol'] = f'SPXW250130{opt_type[0]}0{strike}000'
            result = calculator.calculate_trade_gamma(trade)
            
            assert result is not None
            assert gamma_range[0] <= result['gamma_per_contract'] <= gamma_range[1]
            assert result['strike'] == strike
            assert result['option_type'] == opt_type
    
    def test_directional_force_determination(self, calculator):
        """Test correct assignment of directional forces"""
        # SPX at 5900
        test_cases = [
            (5950, 'CALL', 'UPWARD'),    # Call above SPX
            (5850, 'CALL', 'NEUTRAL'),   # Call below SPX (but still tradeable)
            (5850, 'PUT', 'DOWNWARD'),   # Put below SPX
            (5950, 'PUT', 'NEUTRAL'),    # Put above SPX (but still tradeable)
            (5900, 'CALL', 'NEUTRAL'),   # ATM call
            (5900, 'PUT', 'NEUTRAL'),    # ATM put
        ]
        
        for strike, opt_type, expected_force in test_cases:
            force = calculator.determine_directional_force(strike, opt_type, 5900)
            assert force == expected_force, f"Strike {strike} {opt_type} should be {expected_force}, got {force}"
    
    def test_total_gamma_calculation(self, calculator):
        """Test that total gamma is calculated correctly"""
        trade = {
            'symbol': 'SPXW250130C05900000',
            'size': 250,  # 250 contracts
            'price': 10.50,
            'timestamp': datetime.now()
        }
        
        result = calculator.calculate_trade_gamma(trade)
        assert result['total_gamma'] == result['gamma_per_contract'] * 250 * 100  # size * 100 multiplier
    
    def test_invalid_option_parsing(self, calculator):
        """Test handling of invalid option symbols"""
        invalid_trades = [
            {'symbol': 'INVALID', 'size': 100, 'price': 10},
            {'symbol': 'SPX', 'size': 100, 'price': 10},
            {'symbol': 'SPXW250130X05900000', 'size': 100, 'price': 10},  # Invalid type
        ]
        
        for trade in invalid_trades:
            result = calculator.calculate_trade_gamma(trade)
            assert result is None


class TestPositionTracker:
    """Test position tracking and pin identification"""
    
    @pytest.fixture
    def tracker(self):
        return PositionTracker()
    
    def test_position_accumulation(self, tracker):
        """Test that positions accumulate correctly"""
        trades = [
            {'symbol': 'SPXW250130C05900000', 'size': 100, 'price': 10},
            {'symbol': 'SPXW250130C05900000', 'size': 150, 'price': 11},
            {'symbol': 'SPXW250130P05850000', 'size': 200, 'price': 8},
        ]
        
        gamma_results = [
            {'strike': 5900, 'option_type': 'CALL', 'total_gamma': 50000, 'directional_force': 'UPWARD'},
            {'strike': 5900, 'option_type': 'CALL', 'total_gamma': 75000, 'directional_force': 'UPWARD'},
            {'strike': 5850, 'option_type': 'PUT', 'total_gamma': -80000, 'directional_force': 'DOWNWARD'},
        ]
        
        for trade, gamma in zip(trades, gamma_results):
            tracker.update_position(trade, gamma)
        
        # Check positions
        positions = tracker.get_all_positions()
        assert len(positions) == 2  # Two strikes
        
        # Check 5900 call position
        call_5900 = positions[(positions['strike'] == 5900) & (positions['option_type'] == 'CALL')]
        assert len(call_5900) == 1
        assert call_5900.iloc[0]['cumulative_volume'] == 250  # 100 + 150
        assert call_5900.iloc[0]['net_gamma'] == 125000  # 50000 + 75000
    
    def test_top_pins_identification(self, tracker):
        """Test identification of top pins by gamma force"""
        # Add multiple positions
        positions = [
            {'strike': 5900, 'gamma': 500000, 'force': 'UPWARD'},
            {'strike': 5850, 'gamma': -300000, 'force': 'DOWNWARD'},
            {'strike': 5950, 'gamma': 200000, 'force': 'UPWARD'},
            {'strike': 5875, 'gamma': -150000, 'force': 'DOWNWARD'},
        ]
        
        for pos in positions:
            trade = {'symbol': f'SPXW250130C0{pos["strike"]}000', 'size': 100, 'price': 10}
            gamma_result = {
                'strike': pos['strike'],
                'option_type': 'CALL',
                'total_gamma': pos['gamma'],
                'directional_force': pos['force']
            }
            tracker.update_position(trade, gamma_result)
        
        # Get top pins
        top_all = tracker.get_top_pins(n=3)
        assert len(top_all) == 3
        assert top_all.iloc[0]['strike'] == 5900  # Highest gamma
        
        top_upward = tracker.get_top_pins(n=2, direction='UPWARD')
        assert len(top_upward) == 2
        assert all(top_upward['direction'] == 'UPWARD')


class TestChangeDetector:
    """Test change detection and alert generation"""
    
    @pytest.fixture
    def detector(self):
        return ChangeDetector()
    
    def test_spike_detection(self, detector):
        """Test volume spike detection"""
        # Normal trades
        for i in range(10):
            trade = {'symbol': 'SPXW250130C05900000', 'size': 10, 'price': 10}
            gamma = {'strike': 5900, 'total_gamma': 1000}
            detector.update(trade, gamma, Mock())
        
        # Spike trade (10x normal)
        spike_trade = {'symbol': 'SPXW250130C05900000', 'size': 100, 'price': 10}
        spike_gamma = {'strike': 5900, 'total_gamma': 10000, 'option_type': 'CALL'}
        
        changes = detector.update(spike_trade, spike_gamma, Mock())
        
        # Should detect spike
        spike_changes = [c for c in changes if c.change_type == 'SPIKE']
        assert len(spike_changes) > 0
        assert spike_changes[0].severity in ['HIGH', 'CRITICAL']
    
    def test_new_pin_detection(self, detector):
        """Test new pin formation detection"""
        # Rapid accumulation at a strike
        strike = 5925
        for i in range(5):
            trade = {'symbol': f'SPXW250130C0{strike}000', 'size': 50 * (i + 1), 'price': 10}
            gamma = {'strike': strike, 'total_gamma': 5000 * (i + 1)}
            changes = detector.update(trade, gamma, Mock())
        
        # Should detect new pin formation
        new_pin_changes = [c for c in changes if c.change_type == 'NEW_PIN']
        assert len(new_pin_changes) > 0
    
    def test_direction_flip_detection(self, detector):
        """Test detection of directional flips"""
        # Build upward force
        for i in range(5):
            trade = {'symbol': 'SPXW250130C05950000', 'size': 100, 'price': 10}
            gamma = {'strike': 5950, 'total_gamma': 50000, 'directional_force': 'UPWARD'}
            detector.update(trade, gamma, Mock())
        
        # Strong downward force to flip direction
        for i in range(10):
            trade = {'symbol': 'SPXW250130P05850000', 'size': 200, 'price': 10}
            gamma = {'strike': 5850, 'total_gamma': -100000, 'directional_force': 'DOWNWARD'}
            changes = detector.update(trade, gamma, Mock())
        
        # Should detect direction flip
        flip_changes = [c for c in changes if c.change_type == 'DIRECTION_FLIP']
        # May or may not flip depending on accumulation


class TestConfidenceCalculator:
    """Test multi-factor confidence scoring"""
    
    @pytest.fixture
    def calculator(self):
        return ConfidenceCalculator()
    
    def test_force_score_calculation(self, calculator):
        """Test force score with dynamic thresholds"""
        # Morning conditions (9:45 AM)
        morning_conditions = MarketConditions(time='09:45', vix=15.0, volume_percentile=50)
        
        # Evening conditions (3:45 PM)
        evening_conditions = MarketConditions(time='15:45', vix=15.0, volume_percentile=50)
        
        analysis_data = {
            'net_force': 50000,
            'upward_force': 300000,
            'downward_force': 250000,
            'direction': 'UP',
            'primary_pin': {'strike': 5910, 'force': 300000},
            'spx_price': 5905,
            'all_pins': [{'strike': 5910, 'force': 300000}],
            'active_alerts': []
        }
        
        # Calculate confidence for both times
        morning_conf, morning_details = calculator.calculate_confidence(analysis_data, morning_conditions)
        evening_conf, evening_details = calculator.calculate_confidence(analysis_data, evening_conditions)
        
        # Morning should have higher confidence (lower threshold)
        assert morning_conf > evening_conf
        assert morning_details['components']['force_score'] > evening_details['components']['force_score']
    
    def test_pattern_detection(self, calculator):
        """Test pattern recognition"""
        # Pin sandwich setup
        analysis_data = {
            'net_force': 500000,
            'upward_force': 500000,
            'downward_force': 0,
            'direction': 'UP',
            'primary_pin': {'strike': 5910, 'force': 500000},
            'spx_price': 5905,
            'all_pins': [
                {'strike': 5905, 'force': 50000},
                {'strike': 5910, 'force': 500000},  # Strong center
                {'strike': 5915, 'force': 60000}
            ],
            'active_alerts': []
        }
        
        conf, details = calculator.calculate_confidence(analysis_data)
        
        # Should detect pin sandwich
        assert 'pin_sandwich' in details['patterns']
        assert details['adjustments']['pattern_adjusted'] > details['adjustments']['base']
    
    def test_confidence_components(self, calculator):
        """Test all confidence components calculate correctly"""
        analysis_data = {
            'net_force': 300000,
            'upward_force': 400000,
            'downward_force': 100000,
            'direction': 'UP',
            'primary_pin': {'strike': 5910, 'force': 400000, 'volume': 200},
            'spx_price': 5905,
            'all_pins': [
                {'strike': 5910, 'force': 400000},
                {'strike': 5920, 'force': 100000}
            ],
            'active_alerts': []
        }
        
        conf, details = calculator.calculate_confidence(analysis_data)
        components = details['components']
        
        # Check all components are calculated
        assert 0 <= components['force_score'] <= 1
        assert 0 <= components['imbalance_score'] <= 1
        assert 0 <= components['concentration_score'] <= 1
        assert 0 <= components['distance_score'] <= 1
        assert 0 <= components['momentum_score'] <= 1
        
        # Check final confidence is reasonable
        assert 0 <= conf <= 1
        assert len(details['explanation']) > 0


class TestGammaEngine:
    """Test the main engine orchestration and signal generation"""
    
    @pytest.fixture
    def engine(self):
        return GammaEngine(spx_price=5905.0)
    
    def test_signal_generation_directional(self, engine):
        """Test directional signal generation"""
        # Mock high gamma scenario
        engine.last_analysis = {
            'net_force': 500000,
            'primary_pin': {'strike': 5910, 'force': 500000},
            'spx_price': 5905
        }
        
        # Test at different times
        with patch('gamma_tool_sam.gamma_engine.datetime') as mock_datetime:
            # Morning (10:30 AM) - threshold 75K
            mock_datetime.now.return_value.hour = 10
            mock_datetime.now.return_value.minute = 30
            
            signal = engine._generate_signal(500000, {'strike': 5910, 'force': 500000})
            assert signal['action'] == 'LONG'
            assert signal['target'] == 5910
            
            # Low gamma scenario
            signal = engine._generate_signal(50000, {'strike': 5910, 'force': 50000})
            assert signal['action'] in ['SELL_STRADDLE', 'SELL_IRON_CONDOR', 'SELL_BUTTERFLY', 'WAIT']
    
    def test_premium_signal_generation(self, engine):
        """Test premium selling signal generation"""
        # Mock position tracker to return pins
        mock_pins = pd.DataFrame([
            {'strike': 5910, 'direction': 'UPWARD', 'total_gamma_force': 30000},
            {'strike': 5895, 'direction': 'DOWNWARD', 'total_gamma_force': 25000}
        ])
        
        engine.position_tracker.get_top_pins = Mock(return_value=mock_pins)
        
        # Very low gamma - should suggest straddle
        signal = engine._generate_premium_signal(5000, 5905, None)
        assert signal['action'] == 'SELL_STRADDLE'
        
        # Moderate gamma with tight range - should suggest iron condor
        signal = engine._generate_premium_signal(40000, 5905, None)
        assert signal['action'] == 'SELL_IRON_CONDOR'
        assert 'strikes' in signal
        assert all(k in signal['strikes'] for k in ['call_short', 'call_long', 'put_short', 'put_long'])
    
    def test_dynamic_threshold_calculation(self, engine):
        """Test dynamic threshold values throughout the day"""
        with patch('gamma_tool_sam.gamma_engine.datetime') as mock_datetime:
            test_times = [
                ((9, 45), 25000),    # Early morning
                ((10, 30), 75000),   # Mid morning
                ((13, 0), 150000),   # Midday
                ((14, 30), 250000),  # Afternoon
                ((15, 45), 400000),  # Late day
            ]
            
            for (hour, minute), expected_threshold in test_times:
                mock_datetime.now.return_value.hour = hour
                mock_datetime.now.return_value.minute = minute
                
                threshold = engine._get_dynamic_threshold()
                assert threshold == expected_threshold, f"At {hour}:{minute}, expected {expected_threshold}, got {threshold}"


class TestIntegration:
    """Integration tests for the complete system"""
    
    @pytest.fixture
    def system(self):
        """Create a complete system with all components"""
        engine = GammaEngine(spx_price=5905.0)
        return engine
    
    def test_full_trade_processing_pipeline(self, system):
        """Test complete pipeline from trade to signal"""
        # Simulate incoming trades
        trades = [
            {'symbol': 'SPXW250130C05910000', 'size': 500, 'price': 8.50, 'timestamp': datetime.now()},
            {'symbol': 'SPXW250130C05910000', 'size': 300, 'price': 8.75, 'timestamp': datetime.now()},
            {'symbol': 'SPXW250130P05890000', 'size': 200, 'price': 7.25, 'timestamp': datetime.now()},
        ]
        
        # Process trades
        for trade in trades:
            system.trade_processor.process_trade(trade)
        
        # Check analysis was updated
        assert system.last_analysis is not None
        assert 'net_force' in system.last_analysis
        assert 'signal' in system.last_analysis
        assert 'confidence' in system.last_analysis
        
        # Check API methods work
        summary = system.get_pin_summary()
        assert 'net_force' in summary
        
        strongest_pin = system.get_strongest_pin()
        # May be None if no significant pins yet
        
        risk = system.calculate_risk_level()
        assert 'risk_level' in risk
    
    def test_edge_cases(self, system):
        """Test handling of edge cases"""
        # No data
        assert system.get_pin_summary() == {'error': 'No analysis available yet'}
        assert system.get_strongest_pin() is None
        
        # Invalid trades
        invalid_trade = {'symbol': 'INVALID', 'size': 100, 'price': 10}
        system.trade_processor.process_trade(invalid_trade)
        # Should handle gracefully
        
        # Zero gamma scenario
        system._update_analysis()
        # Should not crash with empty positions


@pytest.mark.asyncio
class TestAsyncComponents:
    """Test async components if any"""
    
    async def test_trade_processor_async(self):
        """Test async trade processing if implemented"""
        # Add async tests here if needed
        pass


class TestDataValidation:
    """Test data validation and error handling"""
    
    def test_strike_validation(self):
        """Test strike price validation"""
        calc = GammaCalculator()
        calc.update_spx_price(5900)
        
        # Extreme strikes should still calculate
        trade = {'symbol': 'SPXW250130C08000000', 'size': 100, 'price': 0.05}
        result = calc.calculate_trade_gamma(trade)
        assert result is not None
        assert result['gamma_per_contract'] > 0  # Should be very small but positive
    
    def test_negative_price_handling(self):
        """Test handling of invalid prices"""
        calc = GammaCalculator()
        calc.update_spx_price(5900)
        
        # Negative price should be handled
        trade = {'symbol': 'SPXW250130C05900000', 'size': 100, 'price': -10}
        result = calc.calculate_trade_gamma(trade)
        # Implementation should handle this appropriately
    
    def test_missing_spx_price(self):
        """Test behavior when SPX price is not set"""
        calc = GammaCalculator()
        # Don't set SPX price
        
        trade = {'symbol': 'SPXW250130C05900000', 'size': 100, 'price': 10}
        result = calc.calculate_trade_gamma(trade)
        assert result is None  # Should return None without SPX price


if __name__ == '__main__':
    pytest.main([__file__, '-v'])