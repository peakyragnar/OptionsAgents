#!/usr/bin/env python3
import sys
sys.path.append('src')

from enhanced_pin_detection import create_enhanced_pin_detector, Trade
from datetime import datetime

def test_system():
    print("🧪 Testing Enhanced Pin Detection System...")
    
    detector = create_enhanced_pin_detector("data/test_enhanced_pins.db")
    detector.update_spx_level(5893.50, "test")
    
    # Test trades
    test_trades = [
        Trade("O:SPX240529C05900000", 5900, 2.50, 25, datetime.now(), True, 5893.50),
        Trade("O:SPX240529C05910000", 5910, 1.80, 35, datetime.now(), True, 5893.50),
        Trade("O:SPX240529P05880000", 5880, 3.20, 20, datetime.now(), False, 5893.50),
        Trade("O:SPX240529C05900000", 5900, 2.60, 50, datetime.now(), True, 5893.50),
    ]
    
    for trade in test_trades:
        detector.process_trade(trade)
    
    analysis = detector.generate_enhanced_analysis(save_to_db=False)
    print(analysis)

if __name__ == "__main__":
    test_system()