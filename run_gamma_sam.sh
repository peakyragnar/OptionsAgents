#!/bin/bash
# Quick launcher for Gamma Tool Sam

echo "🎯 GAMMA TOOL SAM - Quick Start"
echo "=============================="
echo ""
echo "Choose mode:"
echo "1) Standalone Dashboard (no trades, just display)"
echo "2) Full Integration (requires main system running)"
echo ""
read -p "Enter choice (1 or 2): " choice

case $choice in
  1)
    echo "Starting standalone dashboard..."
    python gamma_sam_standalone.py
    ;;
  2)
    echo "Starting full integration mode..."
    echo ""
    echo "⚠️  Make sure 'python -m src.cli live' is running in another terminal!"
    echo ""
    sleep 2
    python gamma_tool_sam_web.py
    ;;
  *)
    echo "Invalid choice"
    exit 1
    ;;
esac