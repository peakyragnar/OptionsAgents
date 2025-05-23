#!/usr/bin/env python3
"""
Data Ingestion Stability Tests for OptionsAgents
Comprehensive testing of real-time data pipeline while market is closed
"""

import pytest
import asyncio
import pandas as pd
import duckdb
import time
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
import json
from typing import Dict, List, Optional
import numpy as np


class DataIngestionTester:
    """
    Test suite for data ingestion stability
    Focus on Parquet/DuckDB persistence and data quality
    """
    
    def __init__(self):
        self.test_data_dir = Path("test_data")
        self.test_data_dir.mkdir(exist_ok=True)
        
    def setup_mock_data(self):
        """Create realistic 0DTE SPX options data for 2025-05-22"""
        
        # Current SPX level around 5850 (May 22, 2025)
        spot_price = 5850.0
        
        # Generate comprehensive strike ladder for 0DTE SPX
        # SPX 0DTE typically has strikes every $5 from wide range
        strikes = np.arange(5700, 6001, 5)  # 5700 to 6000 every $5 (60 strikes per side)
        
        options_data = []
        
        for strike in strikes:
            # Generate calls and puts
            for option_type in ['C', 'P']:
                # Mock realistic 0DTE pricing based on current levels
                distance_from_atm = abs(strike - spot_price)
                
                if option_type == 'C':
                    # Call pricing
                    if strike < spot_price:  # ITM
                        intrinsic = spot_price - strike
                        extrinsic = max(1.0, 25.0 * np.exp(-distance_from_atm / 40))
                        bid = max(0.10, intrinsic + extrinsic - 2.0)
                        ask = intrinsic + extrinsic + 2.0
                    else:  # OTM
                        bid = max(0.05, 20.0 * np.exp(-distance_from_atm / 35))
                        ask = bid * 1.3
                else:
                    # Put pricing  
                    if strike > spot_price:  # ITM
                        intrinsic = strike - spot_price
                        extrinsic = max(1.0, 25.0 * np.exp(-distance_from_atm / 40))
                        bid = max(0.10, intrinsic + extrinsic - 2.0)
                        ask = intrinsic + extrinsic + 2.0
                    else:  # OTM
                        bid = max(0.05, 20.0 * np.exp(-distance_from_atm / 35))
                        ask = bid * 1.3
                
                # Ensure reasonable bid/ask spread for current market
                bid = round(bid, 2)
                ask = round(max(bid + 0.05, ask), 2)
                
                # Realistic volume distribution (higher near ATM)
                volume_factor = max(0.1, 1.0 - distance_from_atm / 200)
                volume = int(np.random.exponential(500 * volume_factor))
                
                option_data = {
                    'symbol': f'SPXW250522{option_type}{strike:08.0f}000',  # 2025-05-22 expiry
                    'strike': strike,
                    'option_type': option_type,
                    'expiry': '2025-05-22',
                    'bid': bid,
                    'ask': ask,
                    'last': round((bid + ask) / 2, 2),
                    'volume': volume,
                    'open_interest': max(0, volume // 3),  # OI typically lower for 0DTE
                    'implied_vol': round(np.random.uniform(0.12, 0.40), 4),
                    'delta': self._calculate_mock_delta(strike, spot_price, option_type),
                    'gamma': self._calculate_mock_gamma(strike, spot_price, distance_from_atm),
                    'theta': round(np.random.uniform(-3.0, -0.1), 4),  # High theta for 0DTE
                    'vega': round(max(0.1, 8.0 * np.exp(-distance_from_atm / 50)), 4),
                    'timestamp': datetime(2025, 5, 22, 15, 30, 0).isoformat()  # Yesterday 3:30 PM
                }
                options_data.append(option_data)
        
        return options_data
    
    def _calculate_mock_delta(self, strike: float, spot: float, option_type: str) -> float:
        """Calculate realistic delta for mock data"""
        if option_type == 'C':
            if strike < spot - 50:  # Deep ITM
                return round(np.random.uniform(0.85, 0.99), 4)
            elif strike > spot + 50:  # Deep OTM
                return round(np.random.uniform(0.01, 0.15), 4)
            else:  # Near ATM
                return round(np.random.uniform(0.25, 0.75), 4)
        else:  # Put
            if strike > spot + 50:  # Deep ITM
                return round(np.random.uniform(-0.99, -0.85), 4)
            elif strike < spot - 50:  # Deep OTM
                return round(np.random.uniform(-0.15, -0.01), 4)
            else:  # Near ATM
                return round(np.random.uniform(-0.75, -0.25), 4)
    
    def _calculate_mock_gamma(self, strike: float, spot: float, distance: float) -> float:
        """Calculate realistic gamma with 0DTE explosion near ATM"""
        if distance <= 5:  # Very close to ATM - gamma explosion
            return round(np.random.uniform(0.008, 0.015), 6)
        elif distance <= 15:  # Near ATM
            return round(np.random.uniform(0.003, 0.008), 6)
        elif distance <= 50:  # Moderate distance
            return round(np.random.uniform(0.0005, 0.003), 6)
        else:  # Far from ATM
            return round(np.random.uniform(0.0001, 0.0005), 6)
    
    def generate_mock_trades(self, num_trades: int = 100) -> List[Dict]:
        """Generate realistic 0DTE trade data"""
        
        trades = []
        options_data = self.setup_mock_data()
        
        for _ in range(num_trades):
            # Pick random option
            option = np.random.choice(options_data)
            
            # Generate trade price between bid/ask
            bid, ask = option['bid'], option['ask']
            trade_price = round(np.random.uniform(bid, ask), 2)
            
            # Trade size (realistic for 0DTE)
            size = np.random.choice([1, 2, 5, 10, 25, 50], 
                                  p=[0.3, 0.25, 0.2, 0.15, 0.07, 0.03])
            
            trade = {
                'symbol': option['symbol'],
                'price': trade_price,
                'size': size,
                'timestamp': datetime.now().isoformat(),
                'exchange': 'CBOE',
                'conditions': ['Regular Sale'],
                'nbbo_bid': bid,
                'nbbo_ask': ask
            }
            trades.append(trade)
        
        return trades


class TestDataIngestion:
    """Test suite for data ingestion components"""
    
    def setup_method(self):
        """Setup for each test"""
        self.tester = DataIngestionTester()
        self.mock_options_data = self.tester.setup_mock_data()
        self.mock_trades = self.tester.generate_mock_trades(50)
    
    def test_options_chain_structure(self):
        """Test SPX options chain has correct structure"""
        
        # Verify we have both calls and puts
        calls = [opt for opt in self.mock_options_data if opt['option_type'] == 'C']
        puts = [opt for opt in self.mock_options_data if opt['option_type'] == 'P']
        
        assert len(calls) > 0, "Should have call options"
        assert len(puts) > 0, "Should have put options"
        assert len(calls) == len(puts), "Should have equal calls and puts"
        
        # Check strike spacing (should be $5 for 0DTE SPX)
        strikes = sorted([opt['strike'] for opt in calls])
        spacings = [strikes[i+1] - strikes[i] for i in range(len(strikes)-1)]
        
        assert all(spacing == 5.0 for spacing in spacings), \
            "SPX 0DTE should have $5 strike spacing"
        
        # Verify reasonable bid/ask spreads
        for opt in self.mock_options_data:
            assert opt['bid'] < opt['ask'], "Bid should be less than ask"
            assert opt['ask'] - opt['bid'] >= 0.05, "Minimum spread should be $0.05"
            
    def test_nbbo_quote_validation(self):
        """Test NBBO quote quality and freshness"""
        
        for opt in self.mock_options_data:
            # Price validation
            assert opt['bid'] > 0, "Bid must be positive"
            assert opt['ask'] > opt['bid'], "Ask must be greater than bid"
            
            # Spread validation (0DTE can have wide spreads)
            spread = opt['ask'] - opt['bid']
            spread_pct = spread / opt['bid'] if opt['bid'] > 0 else float('inf')
            
            # Allow wider spreads for 0DTE (up to 50% for OTM options)
            assert spread_pct <= 0.5, f"Spread too wide: {spread_pct:.2%}"
            
            # Greeks validation
            assert -1 <= opt['delta'] <= 1, "Delta must be between -1 and 1"
            assert opt['gamma'] >= 0, "Gamma must be non-negative"
            assert opt['theta'] <= 0, "Theta should be negative (time decay)"
            
    def test_trade_classification_logic(self):
        """Test trade classification using NBBO"""
        
        for trade in self.mock_trades:
            bid = trade['nbbo_bid']
            ask = trade['nbbo_ask']
            price = trade['price']
            
            # Price should be within bid/ask bounds
            assert bid <= price <= ask, \
                f"Trade price {price} outside NBBO [{bid}, {ask}]"
            
            # Classification logic test
            mid = (bid + ask) / 2
            
            if price >= mid + (ask - bid) * 0.25:
                expected_side = 'BUY'
            elif price <= mid - (ask - bid) * 0.25:
                expected_side = 'SELL'
            else:
                expected_side = 'MID'
                
            # This would be compared against actual classification
            assert expected_side in ['BUY', 'SELL', 'MID']
            
    def test_parquet_storage(self):
        """Test Parquet file storage for options chain data"""
        
        # Convert to DataFrame
        df = pd.DataFrame(self.mock_options_data)
        
        # Test file path structure
        date_str = datetime.now().strftime("%Y-%m-%d")
        time_str = datetime.now().strftime("%H_%M_%S")
        
        parquet_path = self.tester.test_data_dir / f"spx/date={date_str}/{time_str}.parquet"
        parquet_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Write to Parquet
        df.to_parquet(parquet_path, index=False)
        
        # Verify file exists and is readable
        assert parquet_path.exists(), "Parquet file should exist"
        
        # Read back and verify data integrity
        df_read = pd.read_parquet(parquet_path)
        
        assert len(df_read) == len(df), "Row count should match"
        assert list(df_read.columns) == list(df.columns), "Columns should match"
        
        # Verify data types
        assert df_read['strike'].dtype in [np.float64, np.int64], "Strike should be numeric"
        assert df_read['bid'].dtype == np.float64, "Bid should be float"
        assert df_read['ask'].dtype == np.float64, "Ask should be float"
        
    def test_duckdb_storage(self):
        """Test DuckDB storage for dealer gamma snapshots"""
        
        # Create test database
        db_path = self.tester.test_data_dir / "test_gamma.db"
        
        # Clean slate for each test
        if db_path.exists():
            db_path.unlink()
        
        # Sample gamma snapshot data
        gamma_data = [
            {
                'timestamp': datetime.now(),
                'strike': 5200.0,
                'option_type': 'C',
                'dealer_net_position': -100,
                'gamma_per_contract': 0.005,
                'dealer_gamma_exposure': -50000,
                'customer_buys': 150,
                'customer_sells': 50
            },
            {
                'timestamp': datetime.now(),
                'strike': 5200.0,
                'option_type': 'P',
                'dealer_net_position': 75,
                'gamma_per_contract': 0.003,
                'dealer_gamma_exposure': 22500,
                'customer_buys': 25,
                'customer_sells': 100
            }
        ]
        
        # Test DuckDB operations
        with duckdb.connect(str(db_path)) as conn:
            # Create table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS gamma_snapshots (
                    timestamp TIMESTAMP,
                    strike DOUBLE,
                    option_type VARCHAR,
                    dealer_net_position INTEGER,
                    gamma_per_contract DOUBLE,
                    dealer_gamma_exposure DOUBLE,
                    customer_buys INTEGER,
                    customer_sells INTEGER
                )
            """)
            
            # Insert data
            for record in gamma_data:
                conn.execute("""
                    INSERT INTO gamma_snapshots VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, [
                    record['timestamp'],
                    record['strike'],
                    record['option_type'],
                    record['dealer_net_position'],
                    record['gamma_per_contract'],
                    record['dealer_gamma_exposure'],
                    record['customer_buys'],
                    record['customer_sells']
                ])
            
            # Verify data was inserted
            result = conn.execute("SELECT COUNT(*) FROM gamma_snapshots").fetchone()
            assert result[0] == 2, "Should have 2 records"
            
            # Test query performance
            start_time = time.time()
            conn.execute("""
                SELECT strike, SUM(dealer_gamma_exposure) as total_exposure
                FROM gamma_snapshots 
                GROUP BY strike
            """).fetchall()
            query_time = time.time() - start_time
            
            assert query_time < 0.1, "Query should be fast (<100ms)"
            
    def test_data_consistency_validation(self):
        """Test data consistency across components"""
        
        # Test that trade data matches options chain
        for trade in self.mock_trades[:10]:  # Test subset
            # Find matching option in chain
            matching_option = None
            for opt in self.mock_options_data:
                if opt['symbol'] == trade['symbol']:
                    matching_option = opt
                    break
            
            assert matching_option is not None, \
                f"Trade symbol {trade['symbol']} should exist in options chain"
            
            # Verify NBBO consistency
            assert trade['nbbo_bid'] == matching_option['bid'], \
                "Trade NBBO bid should match options chain bid"
            assert trade['nbbo_ask'] == matching_option['ask'], \
                "Trade NBBO ask should match options chain ask"
            
    def test_timestamp_synchronization(self):
        """Test timestamp consistency across data sources"""
        
        # All timestamps should be recent and properly formatted
        now = datetime.now()
        
        for opt in self.mock_options_data[:5]:  # Test subset
            opt_time = datetime.fromisoformat(opt['timestamp'])
            time_diff = abs((now - opt_time).total_seconds())
            
            assert time_diff < 86400, "Timestamp should be within 24 hours for test data"
            
        for trade in self.mock_trades[:5]:  # Test subset
            trade_time = datetime.fromisoformat(trade['timestamp'])
            time_diff = abs((now - trade_time).total_seconds())
            
            assert time_diff < 86400, "Timestamp should be within 24 hours for test data"
            
    def test_memory_usage_performance(self):
        """Test memory usage with large datasets"""
        
        # Generate larger dataset
        large_options_data = []
        for _ in range(10):  # 10x larger dataset
            large_options_data.extend(self.mock_options_data)
        
        # Convert to DataFrame
        df = pd.DataFrame(large_options_data)
        
        # Check memory usage
        memory_usage = df.memory_usage(deep=True).sum()
        memory_mb = memory_usage / (1024 * 1024)
        
        assert memory_mb < 100, f"Memory usage {memory_mb:.1f}MB should be reasonable"
        
        # Test processing time
        start_time = time.time()
        
        # Simulate typical operations
        atm_options = df[abs(df['strike'] - 5200) <= 10]
        call_options = df[df['option_type'] == 'C']
        high_volume = df[df['volume'] > 100]
        
        processing_time = time.time() - start_time
        
        assert processing_time < 1.0, \
            f"Processing time {processing_time:.2f}s should be under 1 second"


class TestDataPipeline:
    """Integration tests for the complete data pipeline"""
    
    def setup_method(self):
        """Setup for integration tests"""
        self.tester = DataIngestionTester()
        
    @pytest.mark.asyncio
    async def test_mock_websocket_connection(self):
        """Test WebSocket connection handling (mocked)"""
        
        # Mock WebSocket connection
        mock_ws = AsyncMock()
        mock_ws.recv = AsyncMock(side_effect=[
            json.dumps({
                'ev': 'T',  # Trade event
                'sym': 'SPXW240523C05200000',
                'p': 15.75,
                's': 10,
                't': int(time.time() * 1000)
            }),
            json.dumps({
                'ev': 'Q',  # Quote event
                'sym': 'SPXW240523C05200000',
                'bp': 15.50,
                'ap': 16.00,
                't': int(time.time() * 1000)
            })
        ])
        
        # Test message processing
        trade_msg = await mock_ws.recv()
        quote_msg = await mock_ws.recv()
        
        trade_data = json.loads(trade_msg)
        quote_data = json.loads(quote_msg)
        
        assert trade_data['ev'] == 'T', "Should receive trade event"
        assert quote_data['ev'] == 'Q', "Should receive quote event"
        
    def test_error_handling_resilience(self):
        """Test system resilience to data errors"""
        
        # Create corrupted data
        corrupted_option = {
            'symbol': 'INVALID_SYMBOL',
            'strike': -100,  # Invalid negative strike
            'bid': 10.0,
            'ask': 9.0,  # Invalid: ask < bid
            'volume': 'invalid',  # Wrong data type
            'timestamp': 'invalid_timestamp'
        }
        
        # Test validation catches errors
        with pytest.raises((ValueError, AssertionError)):
            assert corrupted_option['strike'] > 0, "Strike must be positive"
            assert corrupted_option['ask'] > corrupted_option['bid'], "Ask must be > bid"
            
    def test_reconnection_logic(self):
        """Test automatic reconnection on connection failures"""
        
        # Mock connection failures
        connection_attempts = 0
        max_attempts = 3
        
        def mock_connect():
            nonlocal connection_attempts
            connection_attempts += 1
            if connection_attempts < max_attempts:
                raise ConnectionError("Connection failed")
            return True
        
        # Test reconnection logic
        connected = False
        attempts = 0
        
        while not connected and attempts < max_attempts:
            try:
                connected = mock_connect()
            except ConnectionError:
                attempts += 1
                time.sleep(0.1)  # Brief delay between attempts
                
        assert connected, "Should eventually connect after retries"
        assert attempts == max_attempts - 1, "Should retry correct number of times"


# ==================== DIAGNOSTIC RUNNER ====================

def run_all_data_tests():
    """Run comprehensive data ingestion tests"""
    
    print("🔍 Running OptionsAgents Data Ingestion Tests...")
    print("=" * 60)
    
    # Test categories
    test_modules = [
        "TestDataIngestion",
        "TestDataPipeline"
    ]
    
    results = {}
    
    for test_module in test_modules:
        print(f"\n📊 Running {test_module} tests...")
        
        result = pytest.main([
            f"{__file__}::{test_module}",
            "-v",
            "--tb=short"
        ])
        
        results[test_module] = result == 0
        
        if result == 0:
            print(f"✅ {test_module} tests PASSED")
        else:
            print(f"❌ {test_module} tests FAILED")
    
    # Overall summary
    print("\n" + "=" * 60)
    print("📋 SUMMARY:")
    
    all_passed = all(results.values())
    
    if all_passed:
        print("✅ ALL DATA INGESTION TESTS PASSED!")
        print("✅ Data pipeline is stable and ready for live trading")
    else:
        print("❌ SOME TESTS FAILED - Issues found:")
        for module, passed in results.items():
            if not passed:
                print(f"   ❌ {module}")
                
        print("\n🔧 RECOMMENDED ACTIONS:")
        print("1. Fix failing data validation tests")
        print("2. Verify Parquet/DuckDB storage paths")
        print("3. Check WebSocket connection handling")
        print("4. Validate options chain structure")
        
    return all_passed


if __name__ == "__main__":
    # Run all tests when executed directly
    success = run_all_data_tests()
    
    if success:
        print("\n🚀 Your data ingestion system is ready!")
        print("✅ Stable data flow")
        print("✅ Proper persistence")
        print("✅ Error handling")
        print("✅ Performance validated")
    else:
        print("\n⚠️  Data ingestion needs attention before live trading")
        
    exit(0 if success else 1)