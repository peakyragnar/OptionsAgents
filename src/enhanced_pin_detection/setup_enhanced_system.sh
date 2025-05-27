#!/bin/bash

# Setup script for Enhanced Pin Detection System
# Run this from your OptionsAgents root directory

echo "🎯 Setting up Enhanced Pin Detection System..."

# Create directories
echo "📁 Creating directories..."
mkdir -p src/enhanced_pin_detection
mkdir -p data
mkdir -p logs

# Move the enhanced pin detector files
echo "📄 Setting up enhanced pin detector..."

# Create the enhanced pin detector module
cat > src/enhanced_pin_detection/__init__.py << 'EOF'
"""Enhanced Pin Detection System for OptionsAgents"""

from .enhanced_pin_detector import EnhancedPinDetector, Trade, MomentumSignal, create_enhanced_pin_detector
from .integration import (
    initialize_enhanced_pin_detector,
    process_trade_for_pin_detection,
    should_trigger_analysis,
    generate_pin_analysis,
    get_quick_status,
    get_current_spx_level
)

__all__ = [
    'EnhancedPinDetector',
    'Trade',
    'MomentumSignal',
    'create_enhanced_pin_detector',
    'initialize_enhanced_pin_detector',
    'process_trade_for_pin_detection',
    'should_trigger_analysis',
    'generate_pin_analysis',
    'get_quick_status',
    'get_current_spx_level'
]
EOF

# Backup your existing trade_feed.py
echo "💾 Backing up existing trade_feed.py..."
if [ -f "src/stream/trade_feed.py" ]; then
    cp src/stream/trade_feed.py src/stream/trade_feed.py.backup
    echo "✅ Backup created: src/stream/trade_feed.py.backup"
fi

# Create integration guide
cat > ENHANCED_PIN_INTEGRATION.md << 'EOF'
# Enhanced Pin Detection Integration Guide

## Files Added
- `src/enhanced_pin_detection/enhanced_pin_detector.py` - Core detection system
- `src/enhanced_pin_detection/integration.py` - Integration utilities
- `src/enhanced_pin_detection/__init__.py` - Module initialization

## Integration Steps

### 1. Update your trade_feed.py

Add these imports at the top:
```python
from src.enhanced_pin_detection import (
    initialize_enhanced_pin_detector,
    process_trade_for_pin_detection,
    should_trigger_analysis,
    generate_pin_analysis,
    get_current_spx_level
)
```

### 2. Initialize in your main run function:
```python
async def run():
    # Your existing setup...
    
    # Initialize enhanced pin detector
    initialize_enhanced_pin_detector()
    
    trade_count = 0
    
    # Rest of your websocket loop...
```

### 3. Process trades:
```python
for trade in data:
    if trade.get('ev') == 'T':  # Trade event
        trade_count += 1
        
        # Get current SPX level
        current_spx = get_current_spx_level()
        
        # Process through enhanced pin detector
        process_trade_for_pin_detection(trade, current_spx)
        
        # Generate analysis periodically
        if should_trigger_analysis(trade_count):
            print("\\n" + "="*80)
            analysis = generate_pin_analysis()
            print(analysis)
            print("="*80 + "\\n")
```

## Testing

Run the test function:
```bash
cd src/enhanced_pin_detection
python integration.py
```

## Database

The system creates `data/enhanced_pins.db` to store:
- Pin analysis results
- Momentum signals
- Historical confidence data

## Configuration

Edit the config dictionary in EnhancedPinDetector.__init__() to adjust:
- Minimum thresholds
- Time weights
- Strike spacing weights
EOF

# Create a simple test script
cat > test_enhanced_pins.py << 'EOF'
#!/usr/bin/env python3
"""Test script for Enhanced Pin Detection System"""

import sys
import os
sys.path.append('src')

from enhanced_pin_detection import create_enhanced_pin_detector, Trade
from datetime import datetime

def test_system():
    print("🧪 Testing Enhanced Pin Detection System...")
    
    # Create detector
    detector = create_enhanced_pin_detector("data/test_enhanced_pins.db")
    
    # Set SPX level
    detector.update_spx_level(5893.50, "test")
    
    # Create test trades
    test_trades = [
        Trade("O:SPX240529C05900000", 5900, 2.50, 25, datetime.now(), True, 5893.50),
        Trade("O:SPX240529C05910000", 5910, 1.80, 35, datetime.now(), True, 5893.50),
        Trade("O:SPX240529P05880000", 5880, 3.20, 20, datetime.now(), False, 5893.50),
        Trade("O:SPX240529C05900000", 5900, 2.60, 50, datetime.now(), True, 5893.50),
        Trade("O:SPX240529C05905000", 5905, 2.20, 40, datetime.now(), True, 5893.50),
    ]
    
    print(f"📊 Processing {len(test_trades)} test trades...")
    
    # Process trades
    for i, trade in enumerate(test_trades):
        detector.process_trade(trade)
        print(f"  Processed trade {i+1}/{len(test_trades)}")
    
    # Generate analysis
    print("\n🎯 Generating Enhanced Pin Analysis:")
    print("="*80)
    analysis = detector.generate_enhanced_analysis(save_to_db=False)
    print(analysis)
    print("="*80)
    
    print("✅ Test completed successfully!")

if __name__ == "__main__":
    test_system()
EOF

chmod +x test_enhanced_pins.py

# Update requirements if needed
echo "📦 Checking requirements..."
if [ -f "requirements.txt" ]; then
    # Add numpy if not present
    if ! grep -q "numpy" requirements.txt; then
        echo "numpy>=1.21.0" >> requirements.txt
        echo "✅ Added numpy to requirements.txt"
    fi
else
    echo "⚠️  requirements.txt not found. Make sure numpy is installed: pip install numpy"
fi

echo ""
echo "🎉 Enhanced Pin Detection System setup complete!"
echo ""
echo "Next steps:"
echo "1. Review ENHANCED_PIN_INTEGRATION.md for integration details"
echo "2. Test the system: ./test_enhanced_pins.py"
echo "3. Integrate with your existing trade_feed.py"
echo "4. Update your CLI to use the enhanced system"
echo ""
echo "Files created:"
echo "- src/enhanced_pin_detection/ (directory with all modules)"
echo "- ENHANCED_PIN_INTEGRATION.md (integration guide)"
echo "- test_enhanced_pins.py (test script)"
echo ""
echo "Database will be created at: data/enhanced_pins.db"
EOF
