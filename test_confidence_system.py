#!/usr/bin/env python3
"""
Test the sophisticated confidence calculation system
Shows how different scenarios affect confidence
"""

from gamma_tool_sam.gamma_engine import GammaEngine
from gamma_tool_sam.core.confidence_calculator import MarketConditions
import json

def test_confidence_scenarios():
    """Test various market scenarios"""
    
    print("🧪 TESTING SOPHISTICATED CONFIDENCE SYSTEM\n")
    
    # Initialize engine
    engine = GammaEngine(spx_price=5905.0)
    
    # Scenario 1: Strong one-sided gamma
    print("="*60)
    print("SCENARIO 1: Strong One-Sided Gamma")
    print("="*60)
    
    # Simulate trades creating strong upward gamma
    for i in range(10):
        trade = {
            'symbol': f'O:SPXW251230C0{5910*1000:08d}',
            'price': 2.50,
            'size': 100,
            'timestamp': 1234567890 + i,
            'conditions': [],
            'exchange': 'CBOE'
        }
        engine.trade_processor.process_trade(trade)
    
    # Force analysis update
    engine._update_analysis()
    
    # Show results
    analysis = engine.get_confidence_analysis()
    print(f"\nConfidence: {analysis['overall_confidence']:.1%}")
    print("\nComponent Breakdown:")
    for component, data in analysis['components'].items():
        print(f"  {component:15} Score: {data['score']:.2f} (Weight: {data['weight']:.0%})")
    
    print("\nPatterns Detected:", analysis['patterns'])
    print("\nExplanation:")
    for exp in analysis['explanation']:
        print(f"  • {exp}")
    
    # Scenario 2: Competing pins
    print("\n" + "="*60)
    print("SCENARIO 2: Competing Pins (Lower Confidence)")
    print("="*60)
    
    # Add competing downward gamma
    for i in range(8):
        trade = {
            'symbol': f'O:SPXW251230P0{5900*1000:08d}',
            'price': 2.00,
            'size': 100,
            'timestamp': 1234567900 + i,
            'conditions': [],
            'exchange': 'CBOE'
        }
        engine.trade_processor.process_trade(trade)
    
    engine._update_analysis()
    analysis = engine.get_confidence_analysis()
    
    print(f"\nConfidence: {analysis['overall_confidence']:.1%}")
    print("Patterns Detected:", analysis['patterns'])
    print("\nExplanation:")
    for exp in analysis['explanation'][:3]:
        print(f"  • {exp}")
    
    # Scenario 3: Morning vs Afternoon
    print("\n" + "="*60)
    print("SCENARIO 3: Time of Day Impact")
    print("="*60)
    
    # Test morning conditions
    morning = MarketConditions(time="09:45", vix=15.0)
    
    # Manually trigger confidence calculation with morning conditions
    data = {
        'net_force': 500000,
        'upward_force': 600000,
        'downward_force': 100000,
        'direction': 'UP',
        'primary_pin': {'strike': 5910, 'force': 500000},
        'spx_price': 5905,
        'all_pins': [{'strike': 5910, 'force': 500000}],
        'active_alerts': []
    }
    
    morning_conf, morning_details = engine.confidence_calculator.calculate_confidence(data, morning)
    
    # Test afternoon conditions
    afternoon = MarketConditions(time="15:45", vix=15.0)
    afternoon_conf, afternoon_details = engine.confidence_calculator.calculate_confidence(data, afternoon)
    
    print(f"\nSame gamma force at different times:")
    print(f"  Morning (9:45 AM):   {morning_conf:.1%}")
    print(f"  Afternoon (3:45 PM): {afternoon_conf:.1%}")
    print(f"\nDifference: {abs(morning_conf - afternoon_conf):.1%}")
    
    # Scenario 4: High VIX environment
    print("\n" + "="*60)
    print("SCENARIO 4: Market Volatility Impact")
    print("="*60)
    
    low_vix = MarketConditions(time="12:00", vix=12.0)
    high_vix = MarketConditions(time="12:00", vix=25.0)
    
    low_vix_conf, _ = engine.confidence_calculator.calculate_confidence(data, low_vix)
    high_vix_conf, _ = engine.confidence_calculator.calculate_confidence(data, high_vix)
    
    print(f"\nSame setup with different VIX:")
    print(f"  Low VIX (12):  {low_vix_conf:.1%}")
    print(f"  High VIX (25): {high_vix_conf:.1%}")
    print(f"\nDifference: {abs(low_vix_conf - high_vix_conf):.1%}")
    
    # Show dashboard
    print("\n" + "="*60)
    print("FINAL DASHBOARD VIEW:")
    print("="*60)
    engine.print_human_dashboard()

if __name__ == "__main__":
    test_confidence_scenarios()