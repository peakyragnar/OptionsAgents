#!/bin/bash
# Start Options Agents with Gamma Tool Sam integration

echo "🎯 Starting Options Agents with Gamma Tool Sam"
echo "=============================================="
echo ""
echo "This will run:"
echo "  • Quote cache for real-time option quotes"
echo "  • Trade feed streaming from Polygon"
echo "  • Dealer gamma engine"
echo "  • Gamma Tool Sam directional analysis"
echo ""
echo "Dashboard will be available at: http://localhost:8080"
echo ""
echo "Press Ctrl+C to stop"
echo ""

# Make sure we're in the right directory
cd "$(dirname "$0")"

# Activate virtual environment if it exists
if [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
fi

# Run with Gamma Tool Sam enabled
python -m src.cli live --gamma-tool-sam