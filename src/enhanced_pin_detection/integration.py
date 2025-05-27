"""Fixed integration - correct field name"""

import json
from datetime import datetime, timedelta
from typing import Dict, Any
from .enhanced_pin_detector import EnhancedPinDetector, Trade

enhanced_pin_detector = None
cached_spx_level = 5905.77

def initialize_enhanced_pin_detector(db_path: str = "data/enhanced_pins.db"):
    global enhanced_pin_detector
    enhanced_pin_detector = EnhancedPinDetector(db_path)
    enhanced_pin_detector.update_spx_level(cached_spx_level, "system")
    print(f"🎯 Enhanced Pin Detector initialized with SPX {cached_spx_level:.2f}")

def process_trade_for_pin_detection(trade_data: Dict[str, Any], current_spx: float):
    global enhanced_pin_detector
    
    if not enhanced_pin_detector:
        return
        
    try:
        # Use the SPX level passed in
        if current_spx > 5800:
            spx_level = current_spx
        else:
            spx_level = cached_spx_level
        
        # FIXED: Use 'sym' field instead of 'T'
        symbol = trade_data.get('sym', '')
        
        if not (symbol.startswith('O:SPX') or symbol.startswith('O:SPXW')):
            return
            
        try:
            if symbol.startswith('O:SPXW'):
                parts = symbol.split('O:SPXW')[1]
            else:
                parts = symbol.split('O:SPX')[1]
            
            option_type = parts[6]  # C or P
            strike_part = parts[7:]  # Strike * 1000
            strike = float(strike_part) / 1000
            is_call = (option_type == 'C')
            
        except (IndexError, ValueError, TypeError):
            return
        
        # Create trade object
        trade = Trade(
            symbol=symbol,
            strike=strike,
            price=trade_data.get('p', 0),
            volume=trade_data.get('s', 0),
            timestamp=datetime.fromtimestamp(trade_data.get('t', 0) / 1000),
            is_call=is_call,
            underlying_price=spx_level
        )
        
        # Process the trade
        enhanced_pin_detector.process_trade(trade)
        
        # Show first few successful trades
        if enhanced_pin_detector.total_trades_processed <= 5:
            print(f"✅ PROCESSED #{enhanced_pin_detector.total_trades_processed}: {strike} {option_type}, Vol: {trade.volume}")
        
    except Exception as e:
        if enhanced_pin_detector and enhanced_pin_detector.total_trades_processed < 5:
            print(f"❌ Error: {e}")

def should_trigger_analysis(trade_count: int) -> bool:
    return trade_count % 100 == 0

def generate_pin_analysis() -> str:
    global enhanced_pin_detector
    if not enhanced_pin_detector:
        return "❌ Not initialized"
    try:
        return enhanced_pin_detector.generate_enhanced_analysis(save_to_db=False)
    except Exception as e:
        return f"❌ Error: {e}"

def get_quick_status() -> Dict[str, Any]:
    global enhanced_pin_detector
    if not enhanced_pin_detector:
        return {"status": "not_initialized"}
    try:
        confidence_data = enhanced_pin_detector.calculate_enhanced_confidence()
        primary_pin_strike, primary_pin_gamma = enhanced_pin_detector.get_primary_pin_target()
        return {
            "status": "active",
            "spx_level": enhanced_pin_detector.current_spx_level,
            "total_confidence": confidence_data['total'],
            "primary_pin": {"strike": primary_pin_strike, "gamma": primary_pin_gamma},
            "trades_processed": enhanced_pin_detector.total_trades_processed,
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}

def get_current_spx_level():
    return cached_spx_level
