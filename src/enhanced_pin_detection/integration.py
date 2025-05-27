"""COMPLETELY TIME-BASED - Debug version"""

import json
from datetime import datetime, timedelta
from typing import Dict, Any
from .enhanced_pin_detector import EnhancedPinDetector, Trade
import threading

enhanced_pin_detector = None
cached_spx_level = 5905.77
last_analysis_time = None
analysis_lock = threading.Lock()

def initialize_enhanced_pin_detector(db_path: str = "data/enhanced_pins.db"):
    global enhanced_pin_detector, last_analysis_time
    enhanced_pin_detector = EnhancedPinDetector(db_path)
    enhanced_pin_detector.update_spx_level(cached_spx_level, "system")
    last_analysis_time = datetime.now()
    print(f"🎯 Enhanced Pin Detector: READY - First analysis in 2 minutes")

def process_trade_for_pin_detection(trade_data: Dict[str, Any], current_spx: float):
    global enhanced_pin_detector
    
    if not enhanced_pin_detector:
        return
        
    # Silent processing
    try:
        spx_level = current_spx if current_spx > 5800 else cached_spx_level
        
        symbol = trade_data.get('sym', '')
        if not (symbol.startswith('O:SPX') or symbol.startswith('O:SPXW')):
            return
            
        if symbol.startswith('O:SPXW'):
            parts = symbol.split('O:SPXW')[1]
        else:
            parts = symbol.split('O:SPX')[1]
        
        option_type = parts[6]
        strike_part = parts[7:]
        strike = float(strike_part) / 1000
        is_call = (option_type == 'C')
        
        trade = Trade(
            symbol=symbol,
            strike=strike,
            price=trade_data.get('p', 0),
            volume=trade_data.get('s', 0),
            timestamp=datetime.fromtimestamp(trade_data.get('t', 0) / 1000),
            is_call=is_call,
            underlying_price=spx_level
        )
        
        enhanced_pin_detector.process_trade(trade)
        
    except Exception:
        pass

def should_trigger_analysis(trade_count: int) -> bool:
    """THREAD-SAFE time-only triggering with debug info"""
    global last_analysis_time
    
    with analysis_lock:
        if last_analysis_time is None:
            return False
            
        now = datetime.now()
        time_elapsed = now - last_analysis_time
        
        # Debug every 1000 calls to see what's happening
        if trade_count % 1000 == 0:
            print(f"🔍 DEBUG: Trade #{trade_count}, Time since last: {time_elapsed.total_seconds():.1f}s")
        
        # Only trigger if 2+ minutes have passed
        if time_elapsed >= timedelta(minutes=2):
            last_analysis_time = now
            print(f"✅ ANALYSIS TRIGGERED at {now.strftime('%H:%M:%S')} (after {time_elapsed.total_seconds():.1f}s)")
            return True
        
        return False

def generate_pin_analysis() -> str:
    """This should ONLY run every 2+ minutes"""
    global enhanced_pin_detector
    
    print(f"🎯 GENERATING ANALYSIS at {datetime.now().strftime('%H:%M:%S')}")
    
    if not enhanced_pin_detector:
        return ""
    
    try:
        confidence_data = enhanced_pin_detector.calculate_enhanced_confidence()
        primary_pin_strike, primary_pin_gamma = enhanced_pin_detector.get_primary_pin_target()
        static_bias = enhanced_pin_detector.get_static_bias()
        momentum_bias = enhanced_pin_detector.get_momentum_bias()
        
        import os
        os.system('clear')
        
        now = datetime.now()
        
        print("🎯" * 50)
        print(f"          ENHANCED SPX PIN ANALYSIS")
        print(f"               {now.strftime('%Y-%m-%d %H:%M:%S')}")
        print("🎯" * 50)
        
        conf_emoji = "🔥" if confidence_data['total'] >= 0.8 else "💪" if confidence_data['total'] >= 0.65 else "📊" if confidence_data['total'] >= 0.5 else "⚠️"
        
        print(f"\n📊 MARKET DATA:")
        print(f"   SPX Level: {enhanced_pin_detector.current_spx_level:.2f}")
        print(f"   Trades Analyzed: {enhanced_pin_detector.total_trades_processed:,}")
        print(f"   System Confidence: {confidence_data['total']:.1%} {conf_emoji}")
        
        print(f"\n🎯 PIN ANALYSIS:")
        print(f"   Primary Target: ${primary_pin_strike:.0f}")
        print(f"   Gamma Concentration: {primary_pin_gamma:.0f} units")
        
        static_emoji = "🚀" if static_bias == "UPWARD" else "📉" if static_bias == "DOWNWARD" else "➡️"
        momentum_emoji = "🚀" if momentum_bias == "UPWARD" else "📉" if momentum_bias == "DOWNWARD" else "➡️"
        
        print(f"\n📈 DIRECTIONAL SIGNALS:")
        print(f"   Pin Bias: {static_bias} {static_emoji}")
        print(f"   Momentum: {momentum_bias} {momentum_emoji}")
        
        if static_bias == momentum_bias:
            if static_bias == "UPWARD":
                signal = "🚀 STRONG BULLISH SIGNAL"
            elif static_bias == "DOWNWARD":
                signal = "📉 STRONG BEARISH SIGNAL"  
            else:
                signal = "😴 NEUTRAL/SIDEWAYS"
        else:
            signal = "⚡ MIXED SIGNALS"
            
        print(f"   Combined: {signal}")
        
        next_time = now + timedelta(minutes=2)
        print(f"\n⏰ TIMING:")
        print(f"   Next Analysis: {next_time.strftime('%H:%M:%S')}")
        
        print("\n" + "🎯" * 50)
        print("System running... (Ctrl+C to stop)")
        print("🎯" * 50 + "\n")
        
        return ""
        
    except Exception as e:
        print(f"❌ Analysis Error: {e}")
        return ""

def get_quick_status_data():
    """Get current status data for quick display"""
    global enhanced_pin_detector, cached_spx_level
    
    if not enhanced_pin_detector:
        return {
            "confidence": 0.0,
            "spx_level": cached_spx_level,
            "trades_processed": 0
        }
    
    try:
        # Get current confidence
        confidence_data = enhanced_pin_detector.calculate_enhanced_confidence()
        total_confidence = confidence_data.get('total', 0.0)
        
        # Get current SPX level
        current_spx = enhanced_pin_detector.current_spx_level
        
        # Get trades processed
        trades_processed = enhanced_pin_detector.total_trades_processed
        
        return {
            "confidence": total_confidence,
            "spx_level": current_spx if current_spx > 0 else cached_spx_level,
            "trades_processed": trades_processed
        }
    except Exception as e:
        print(f"❌ Quick status error: {e}")
        return {
            "confidence": 0.0,
            "spx_level": cached_spx_level,
            "trades_processed": 0
        }

# Update the get_quick_status function to use the new data function
def get_quick_status():
    """Get quick status string for display"""
    data = get_quick_status_data()
    return {
        "status": "active",
        "confidence": data["confidence"],
        "spx_level": data["spx_level"],
        "trades": data["trades_processed"]
    }

def get_current_spx_level():
    return cached_spx_level
