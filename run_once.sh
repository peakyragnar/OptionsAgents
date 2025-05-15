#!/usr/bin/env bash
set -e                      # exit immediately on error
source /Users/michael/OptionsAgents/.venv/bin/activate

# ── Skip when US-equity market is closed ──────────────────────────────
if ! duckdb -c "
  SELECT  EXTRACT('dow', NOW()) BETWEEN 1 AND 5    -- Mon-Fri
     AND EXTRACT('hour', NOW()) BETWEEN 13 AND 20  -- 13-20 UTC (09-16 ET)
"; then
  echo \"$(date '+%T')  SKIP – market closed\" >> data/logs/ingest_$(date +%F).log
  exit 0
fi
# ──────────────────────────────────────────────────────────────────────

# 1. write a snapshot
python src/ingest/snapshot.py

# 2. run the critical health-check test
pytest -q tests/test_bid_ask_not_null.py

# 3. make the new snapshot visible via the view
duckdb market.duckdb -c "
CREATE OR REPLACE VIEW spx_chain AS
SELECT *,
       -- take 8 chars starting 16 from the end: 20_42_52
       substr(filename, -16, 8) AS ts
FROM parquet_scan(
       'data/parquet/spx/date=*/*.parquet',
       filename=true             -- expose filename column
);
"

# 4. simple timestamped log
mkdir -p data/logs
echo \"$(date '+%T')  OK\" >> data/logs/ingest_$(date +%F).log
