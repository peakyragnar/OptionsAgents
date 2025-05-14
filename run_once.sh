#!/usr/bin/env bash
set -e                      # exit immediately on error

# 1. write a snapshot
python src/ingest/snapshot.py

# 2. run the critical health-check test
pytest -q tests/test_bid_ask_not_null.py

# 3. make the new snapshot visible via the view
duckdb market.duckdb -c "
CREATE OR REPLACE VIEW spx_chain AS
SELECT *, substr(file_name, -15, 8) AS ts
FROM parquet_scan('data/parquet/spx/date=*/*.parquet');"

# 4. simple timestamped log
mkdir -p data/logs
echo \"$(date '+%T')  OK\" >> data/logs/ingest_$(date +%F).log
