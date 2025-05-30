"""
Tests for premium selling strategies in Gamma Tool Sam
Validates iron condor, straddle, and butterfly signal generation
"""

import pytest
import pandas as pd
from unittest.mock import Mock, patch
from datetime import datetime

from gamma_tool_sam.gamma_engine import GammaEngine


class TestPremiumSellingStrategies:
    """Test premium selling strategy signal generation"""
    
    @pytest.fixture
    def engine(self):
        engine = GammaEngine(spx_price=5905.0)
        return engine
    
    def test_straddle_signal_conditions(self, engine):
        """Test SELL_STRADDLE signal generation"""
        # Mock very low gamma environment
        mock_pins = pd.DataFrame([
            {'strike': 5910, 'direction': 'UPWARD', 'total_gamma_force': 8000},
            {'strike': 5900, 'direction': 'DOWNWARD', 'total_gamma_force': 7000}
        ])
        
        engine.position_tracker.get_top_pins = Mock(return_value=mock_pins)
        
        # Net force < 10K should trigger straddle
        signal = engine._generate_premium_signal(5000, 5905, None)
        
        assert signal['action'] == 'SELL_STRADDLE'
        assert 'strikes' in signal
        assert 'atm' in signal['strikes']
        assert signal['strikes']['atm'] == 5905  # Rounded to nearest 5
        assert 'upper_bound' in signal
        assert 'lower_bound' in signal
        assert 'execution' in signal
    
    def test_iron_condor_signal_conditions(self, engine):
        """Test SELL_IRON_CONDOR signal generation"""
        # Mock tight range scenario
        mock_pins = pd.DataFrame([
            {'strike': 5915, 'direction': 'UPWARD', 'total_gamma_force': 40000},
            {'strike': 5895, 'direction': 'DOWNWARD', 'total_gamma_force': 35000}
        ])
        
        engine.position_tracker.get_top_pins = Mock(return_value=mock_pins)
        
        # Range width = 20, gamma < 50K
        signal = engine._generate_premium_signal(45000, 5905, None)
        
        assert signal['action'] == 'SELL_IRON_CONDOR'
        assert 'strikes' in signal
        
        # Check strike structure
        strikes = signal['strikes']
        assert all(k in strikes for k in ['call_short', 'call_long', 'put_short', 'put_long'])
        
        # Validate strike relationships
        assert strikes['put_long'] < strikes['put_short'] < strikes['call_short'] < strikes['call_long']
        assert strikes['call_short'] == 5920  # Upper bound + 5
        assert strikes['put_short'] == 5890   # Lower bound - 5
        assert strikes['call_long'] - strikes['call_short'] == 10  # 10 point wings
        assert strikes['put_short'] - strikes['put_long'] == 10
    
    def test_butterfly_signal_conditions(self, engine):
        """Test SELL_BUTTERFLY signal generation"""
        # Mock strong pin near current price
        primary_pin = {'strike': 5910, 'force': 75000}
        
        mock_pins = pd.DataFrame([
            {'strike': 5910, 'direction': 'UPWARD', 'total_gamma_force': 75000},
            {'strike': 5920, 'direction': 'UPWARD', 'total_gamma_force': 20000}
        ])
        
        engine.position_tracker.get_top_pins = Mock(return_value=mock_pins)
        
        # Pin within 10 points of SPX
        signal = engine._generate_premium_signal(45000, 5905, primary_pin)
        
        assert signal['action'] == 'SELL_BUTTERFLY'
        assert 'strikes' in signal
        
        # Check butterfly structure
        strikes = signal['strikes']
        assert 'lower' in strikes
        assert 'center' in strikes
        assert 'upper' in strikes
        
        # Validate strike relationships
        assert strikes['center'] == 5910  # Primary pin
        assert strikes['lower'] == 5900   # Center - 10
        assert strikes['upper'] == 5920   # Center + 10
        assert strikes['upper'] - strikes['center'] == strikes['center'] - strikes['lower']
    
    def test_no_pins_scenario(self, engine):
        """Test when no pins are established"""
        # Empty pins dataframe
        engine.position_tracker.get_top_pins = Mock(return_value=pd.DataFrame())
        
        signal = engine._generate_premium_signal(5000, 5905, None)
        
        assert signal['action'] == 'WAIT'
        assert 'No pins established' in signal['reason']
        assert signal['confidence'] < 0.3
    
    def test_mixed_gamma_scenario(self, engine):
        """Test when gamma is between thresholds"""
        # Mock moderate gamma, wide range
        mock_pins = pd.DataFrame([
            {'strike': 5950, 'direction': 'UPWARD', 'total_gamma_force': 30000},
            {'strike': 5850, 'direction': 'DOWNWARD', 'total_gamma_force': 25000}
        ])
        
        engine.position_tracker.get_top_pins = Mock(return_value=mock_pins)
        
        # Range too wide for iron condor, gamma too high for straddle
        signal = engine._generate_premium_signal(40000, 5905, None)
        
        assert signal['action'] == 'WAIT'
        assert 'no clear premium selling setup' in signal['reason']


class TestDynamicThresholds:
    """Test time-based dynamic threshold adjustments"""
    
    @pytest.fixture
    def engine(self):
        return GammaEngine(spx_price=5905.0)
    
    def test_threshold_progression_through_day(self, engine):
        """Test threshold values throughout trading day"""
        with patch('gamma_tool_sam.gamma_engine.datetime') as mock_datetime:
            # Test each time period
            test_schedule = [
                # (hour, minute, expected_threshold, period_name)
                (9, 35, 25000, "Early morning"),
                (9, 59, 25000, "Still early morning"),
                (10, 0, 75000, "Mid morning start"),
                (10, 45, 75000, "Mid morning"),
                (11, 0, 150000, "Peak hours start"),
                (13, 30, 150000, "Midday"),
                (14, 0, 250000, "Afternoon start"),
                (15, 0, 250000, "Mid afternoon"),
                (15, 30, 400000, "Late day start"),
                (15, 55, 400000, "Near close"),
            ]
            
            for hour, minute, expected, period in test_schedule:
                mock_datetime.now.return_value.hour = hour
                mock_datetime.now.return_value.minute = minute
                
                threshold = engine._get_dynamic_threshold()
                assert threshold == expected, f"{period} ({hour}:{minute:02d}): expected {expected}, got {threshold}"
    
    def test_signal_changes_with_time(self, engine):
        """Test that same gamma force produces different signals at different times"""
        # Fixed gamma force
        net_force = 60000
        primary_pin = {'strike': 5910, 'force': 60000}
        
        signals = {}
        
        with patch('gamma_tool_sam.gamma_engine.datetime') as mock_datetime:
            # Morning - should be directional
            mock_datetime.now.return_value.hour = 9
            mock_datetime.now.return_value.minute = 45
            signals['morning'] = engine._generate_signal(net_force, primary_pin)
            
            # Afternoon - should be premium
            mock_datetime.now.return_value.hour = 15
            mock_datetime.now.return_value.minute = 0
            signals['afternoon'] = engine._generate_signal(net_force, primary_pin)
        
        # Morning: 60K > 25K threshold = directional
        assert signals['morning']['action'] in ['LONG', 'SHORT']
        
        # Afternoon: 60K < 250K threshold = premium or wait
        assert signals['afternoon']['action'] in ['SELL_STRADDLE', 'SELL_IRON_CONDOR', 'SELL_BUTTERFLY', 'WAIT']


class TestSignalConfidence:
    """Test confidence adjustments with dynamic thresholds"""
    
    @pytest.fixture
    def engine(self):
        return GammaEngine(spx_price=5905.0)
    
    def test_confidence_scaling_with_threshold(self, engine):
        """Test that confidence scales properly with dynamic thresholds"""
        primary_pin = {'strike': 5910, 'force': 200000}
        
        with patch('gamma_tool_sam.gamma_engine.datetime') as mock_datetime:
            # Morning signal
            mock_datetime.now.return_value.hour = 9
            mock_datetime.now.return_value.minute = 45
            morning_signal = engine._generate_signal(200000, primary_pin)
            
            # Afternoon signal  
            mock_datetime.now.return_value.hour = 14
            mock_datetime.now.return_value.minute = 30
            afternoon_signal = engine._generate_signal(200000, primary_pin)
        
        # Both should be directional but with different confidence
        assert morning_signal['action'] in ['LONG', 'SHORT']
        assert afternoon_signal['action'] in ['LONG', 'SHORT']
        
        # Morning should have higher confidence (200K/125K vs 200K/1250K)
        # Using threshold * 5 for confidence calculation
        assert morning_signal['confidence'] > afternoon_signal['confidence']
    
    def test_premium_strategy_confidence_levels(self, engine):
        """Test confidence levels for different premium strategies"""
        mock_pins = pd.DataFrame([
            {'strike': 5910, 'direction': 'UPWARD', 'total_gamma_force': 8000},
            {'strike': 5900, 'direction': 'DOWNWARD', 'total_gamma_force': 7000}
        ])
        
        engine.position_tracker.get_top_pins = Mock(return_value=mock_pins)
        
        # Test different scenarios
        scenarios = [
            (5000, 0.7, "SELL_STRADDLE"),    # Very low gamma
            (40000, 0.65, "SELL_IRON_CONDOR"), # Moderate gamma
        ]
        
        for gamma, expected_conf, expected_action in scenarios:
            signal = engine._generate_premium_signal(gamma, 5905, None)
            
            if signal['action'] == expected_action:
                assert signal['confidence'] == expected_conf


class TestRangeCalculations:
    """Test range boundary calculations for premium strategies"""
    
    @pytest.fixture  
    def engine(self):
        return GammaEngine(spx_price=5905.0)
    
    def test_range_boundary_identification(self, engine):
        """Test correct identification of range boundaries"""
        # Various pin configurations
        test_cases = [
            # Single-sided pins
            (
                pd.DataFrame([
                    {'strike': 5920, 'direction': 'UPWARD', 'total_gamma_force': 50000},
                    {'strike': 5925, 'direction': 'UPWARD', 'total_gamma_force': 30000},
                ]),
                None,  # No downward pins
                "Single-sided upward"
            ),
            # Balanced pins
            (
                pd.DataFrame([
                    {'strike': 5920, 'direction': 'UPWARD', 'total_gamma_force': 50000},
                    {'strike': 5890, 'direction': 'DOWNWARD', 'total_gamma_force': 45000},
                    {'strike': 5925, 'direction': 'UPWARD', 'total_gamma_force': 20000},
                    {'strike': 5885, 'direction': 'DOWNWARD', 'total_gamma_force': 15000},
                ]),
                (5920, 5890),  # Expected boundaries
                "Balanced pins"
            ),
        ]
        
        for pins_df, expected_bounds, description in test_cases:
            engine.position_tracker.get_top_pins = Mock(return_value=pins_df)
            
            signal = engine._generate_premium_signal(30000, 5905, None)
            
            if expected_bounds:
                upper, lower = expected_bounds
                if 'upper_bound' in signal:
                    assert signal['upper_bound'] == upper, f"{description}: upper bound"
                    assert signal['lower_bound'] == lower, f"{description}: lower bound"
    
    def test_strike_selection_logic(self, engine):
        """Test strike selection for different strategies"""
        # Iron condor strike selection
        mock_pins = pd.DataFrame([
            {'strike': 5915, 'direction': 'UPWARD', 'total_gamma_force': 40000},
            {'strike': 5895, 'direction': 'DOWNWARD', 'total_gamma_force': 35000}
        ])
        
        engine.position_tracker.get_top_pins = Mock(return_value=mock_pins)
        
        signal = engine._generate_premium_signal(45000, 5905, None)
        
        if signal['action'] == 'SELL_IRON_CONDOR':
            strikes = signal['strikes']
            
            # Wings should be outside pin boundaries
            assert strikes['call_short'] > 5915  # Above upper pin
            assert strikes['put_short'] < 5895   # Below lower pin
            
            # Wings should be symmetric
            call_width = strikes['call_long'] - strikes['call_short']
            put_width = strikes['put_short'] - strikes['put_long']
            assert call_width == put_width == 10


if __name__ == '__main__':
    pytest.main([__file__, '-v'])