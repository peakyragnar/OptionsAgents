#!/usr/bin/env bash
# Activate the project's virtual-env, then run the snapshot job
cd /Users/michael/OptionsAgents           # adjust if your repo lives elsewhere
source .venv/bin/activate
export PYTHONPATH="$PWD:$PYTHONPATH"

# ---- symbols you want to snapshot ----
python -m src.snapshot.refresh_oi --symbols SPY QQQ IWM VIX

# optional: keep a dated log
# python -m src.snapshot.refresh_oi ...  >> logs/refresh_oi_$(date +\%Y-\%m-\%d).log 2>&1