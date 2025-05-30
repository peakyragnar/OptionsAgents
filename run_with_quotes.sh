#!/bin/bash
# Quick fix to run the system with proper quotes

cd /Users/michael/OptionsAgents
source .venv/bin/activate
export POLYGON_KEY=wpVD1X01KQu8pQMp34clrAKQWxTXrB8A

# Kill existing
pkill -f "src.cli live"
sleep 2

echo "Starting Options Agents with working quotes..."
python -m src.cli live