#!/bin/zsh
source ~/.zprofile
cd /Users/michael/OptionsAgents
source .venv/bin/activate
python -c "from src.stream.snapshot_intraday import intraday_snapshot; path = intraday_snapshot(); print(f'Snapshot written to {path}')"