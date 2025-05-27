#!/bin/bash

echo "🚀 Integrating Enhanced Pin Detection with Live Trade Feed..."

# Backup current trade_feed.py
echo "💾 Creating backup..."
cp src/stream/trade_feed.py src/stream/trade_feed.py.backup
echo "✅ Backup created: src/stream/trade_feed.py.backup"

# Create integration instructions
cat > INTEGRATION_INSTRUCTIONS.md << 'EOF'
# Enhanced Pin Detection Integration Instructions

## What to Add to Your trade_feed.py

### 1. Add imports at the top:
```python
from src.enhanced_pin_detection import (
    initialize_enhanced_pin_detector,
    process_trade_for_pin_detection,
    should_trigger_analysis,
    generate_pin_analysis
)
from datetime import datetime, timedelta
```

### 2. Add SPX level detection function:
```python
def get_current_spx_from_quotes():
    """Get SPX from your quote cache"""
    try:
        from src.stream.quote_cache import quotes
        
        spx_symbols = ['I:SPX', 'SPX', '$SPX', 'SPXW']
        for symbol in spx_symbols:
            if symbol in quotes:
                bid, ask, timestamp = quotes[symbol]
                if bid > 0 and ask > 0:
                    return (bid + ask) / 2
    except:
        pass
    return 5900.0  # Fallback
```

### 3. Initialize in your run() function:
```python
async def run():
    # Your existing setup...
    
    # ADD THIS:
    initialize_enhanced_pin_detector("data/live_enhanced_pins.db")
    trade_count = 0
    
    # Rest of your websocket loop...
```

### 4. Process trades in your message loop:
```python
for message in data:
    if message.get('ev') == 'T':  # Trade event
        trade_count += 1
        
        # ADD THIS:
        current_spx = get_current_spx_from_quotes()
        process_trade_for_pin_detection(message, current_spx)
        
        # Your existing processing...
        
        # ADD THIS:
        if should_trigger_analysis(trade_count):
            print("\n" + "="*90)
            analysis = generate_pin_analysis()
            print(analysis)
            print("="*90 + "\n")
```

## Testing Integration

1. Test with your existing system:
```bash
python -m src.cli live
```

2. You should see output like:
```
🎯 Enhanced Pin Detection System initialized
🔍 SPX UPDATE: 0.00 → 5893.50
... (trade processing)
================================================================================
🎯 ENHANCED PIN & MOMENTUM ANALYSIS - 16:45:32
SPX Level: 5893.50
Confidence: 72.4% 💪
🎯 PRIMARY PIN: 5900 (245 gamma units)
⚡ MOMENTUM: Recent activity detected
================================================================================
```

## Troubleshooting

- If SPX level shows 0.00, check your quote cache symbols
- If confidence is very low, system needs more trades to build up data
- Analysis triggers every 100 trades by default

## Files Modified
- `src/stream/trade_feed.py` (backed up to .backup)
- Database created at: `data/live_enhanced_pins.db`
EOF

echo ""
echo "📋 Integration instructions created: INTEGRATION_INSTRUCTIONS.md"
echo ""
echo "🔧 Manual Integration Steps:"
echo "1. Edit src/stream/trade_feed.py"
echo "2. Add the imports and functions from the integration code"
echo "3. Test with: python -m src.cli live"
echo ""
echo "💡 Key Integration Points:"
echo "- Add imports at top of trade_feed.py"
echo "- Initialize enhanced pin detector in run() function"
echo "- Process each trade through pin detector"
echo "- Generate analysis every 100 trades"
echo ""
echo "🎯 Expected Output: Enhanced pin analysis every 100 trades with confidence, pins, and momentum signals"
