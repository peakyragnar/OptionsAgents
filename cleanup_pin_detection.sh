#!/bin/bash
# Quick script to clean up and use ONLY enhanced pin detection

echo "🧹 Cleaning up to use ONLY Enhanced Pin Detection..."

# Backup your current trade_feed.py
cp src/stream/trade_feed.py src/stream/trade_feed.py.backup_$(date +%Y%m%d_%H%M%S)

# Comment out the original directional pin import (line 15)
sed -i '' 's/from src.directional_pin_detector import DIRECTIONAL_PIN_DETECTOR/# from src.directional_pin_detector import DIRECTIONAL_PIN_DETECTOR/' src/stream/trade_feed.py

# Comment out the _last_directional_pin_report variable
sed -i '' 's/_last_directional_pin_report = time.time()/# _last_directional_pin_report = time.time()/' src/stream/trade_feed.py

# Disable initialize_pin_detector call
sed -i '' 's/initialize_pin_detector()/# initialize_pin_detector()  # Disabled - using enhanced only/' src/stream/trade_feed.py

# Clear all caches
rm -rf src/__pycache__
rm -rf src/stream/__pycache__
rm -rf src/enhanced_pin_detection/__pycache__
rm -rf src/dealer/__pycache__

echo "✅ Cleanup complete!"
echo ""
echo "🎯 Now using ONLY Enhanced Pin Detection (every 2 minutes)"
echo ""
echo "📝 Manual check needed:"
echo "   - Open src/stream/trade_feed.py"
echo "   - Search for 'directional' to ensure all old code is disabled"
echo "   - The enhanced system should be the only one running"
echo ""
echo "🚀 Test with: python -m src.cli live"