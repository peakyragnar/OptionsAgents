#!/bin/zsh
source ~/.zprofile
cd /Users/michael/OptionsAgents
source .venv/bin/activate

# Check if we should use REST API simulation
if [[ "$1" == "--rest" ]]; then
  echo "Using REST API simulation mode"
  USE_REST=true python -m src.stream.ws_client
else
  # Try WebSocket first with fallback to REST
  python -m src.stream.ws_client
fi