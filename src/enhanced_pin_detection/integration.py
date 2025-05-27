"""
Integration module for Enhanced Pin Detector with existing trade feed
"""

import json
from datetime import datetime
from typing import Dict, Any
from .enhanced_pin_detector import EnhancedPinDetector, Trade

# Global pin detector instance
enhanced_pin_detector = None

def initialize_enhanced_pin_detector(db_path: str = "data/enhanced_pins.db"):
    """Initialize the enhanced pin detector"""
    global enhanced_pin_detector
    enhanced_pin_detector = EnhancedPinDetector(db_path)
    print("🎯 Enhanced Pin Detector initialized")

def process_trade_for_pin_detection(trade_data: Dict[str, Any], current_spx: float):
    """Process individual trade through enhanced pin detector"""
    global enhanced_pin_detector
    
    if not enhanced_pin_detector:
        return
        
    try:
        # Update SPX level
        if current_spx > 0:
            enhanced_pin_detector.update_spx_level(current_spx, "trade_feed")
        
        # Parse trade data
        symbol = trade_data.get('T', '')
        
        # Only process SPX options
        if not symbol.startswith('O:SPX'):
            return
            
        # Extract strike and option type from symbol
        try:
            parts = symbol.split('O:SPX')[1]
            option_type = parts[6]  # C or P
            strike_part = parts[7:]  # Strike * 1000
            
            strike = float(strike_part) / 1000
            is_call = (option_type == 'C')
            
        except (IndexError, ValueError):
            return
        
        # Create Trade object
        trade = Trade(
            symbol=symbol,
            strike=strike,
            price=trade_data.get('p', 0),
            volume=trade_data.get('s', 0),
            timestamp=datetime.fromtimestamp(trade_data.get('t', 0) / 1000),
            is_call=is_call,
            underlying_price=current_spx
        )
        
        # Process through enhanced detector
        enhanced_pin_detector.process_trade(trade)
        
    except Exception as e:
        print(f"❌ Error processing trade for pin detection: {e}")

def should_trigger_analysis(trade_count: int) -> bool:
    """Determine if we should trigger pin analysis"""
    return trade_count % 100 == 0

def generate_pin_analysis() -> str:
    """Generate and return pin analysis"""
    global enhanced_pin_detector
    
    if not enhanced_pin_detector:
        return "❌ Enhanced Pin Detector not initialized"
        
    try:
        return enhanced_pin_detector.generate_enhanced_analysis(save_to_db=False)
    except Exception as e:
        return f"❌ Error generating pin analysis: {e}"

def get_current_spx_level():
    """Get current SPX level from available sources"""
    # Simple fallback for testing
    return 5893.50

def get_quick_status() -> Dict[str, Any]:
    """Get quick status for logging/debugging"""
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
            "primary_pin": {
                "strike": primary_pin_strike,
                "gamma": primary_pin_gamma
            },
            "trades_processed": enhanced_pin_detector.total_trades_processed,
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}
