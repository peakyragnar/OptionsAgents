Below is a ready-to-paste README.md that you can drop into the root of your OptionsAgents workspace (or view inside any IDE).
It documents the project’s purpose, architecture, directory layout, environment setup, daily usage, and the test/CI pipeline we have implemented so far.

⸻


# OptionsAgents – 0-DTE SPY Trading Agent (Phase 1)

## Purpose
Automate the data-collection and analytics pipeline required for a
dealer-gamma-aware 0-DTE SPY options strategy, using:
* **Parquet snapshots** for raw minute data  
* **DuckDB** for fast local analytics  
* **Polygon.io** as the market-data source  
* A staged roll-out towards an agentic trading system (planner, risk-guard, execution)

**Current milestone:**  
*Ingest minute snapshots of the SPX 0-DTE option chain, store them in a partitioned Parquet layout, and prove the data are readable via DuckDB and unit-tests.*

---

## Directory Layout (phase 1)

OptionsAgents/
├── data/
│   └── parquet/                # append-only raw snapshots
│       └── spx/
│           └── date=YYYY-MM-DD/
│               └── HH_MM_SS.parquet
├── src/
│   └── ingest/
│       └── snapshot.py         # pulls one SPX snapshot & writes Parquet
├── tests/
│   └── test_snapshot.py        # two unit tests (file exists, duckdb query)
├── .env                        # your Polygon key (ignored in Git)
├── .env.example                # template, committed
├── .gitignore
└── README.md

---

## Environment Setup (macOS / zsh)

```bash
# 1. clone repo and enter dir
git clone <url> OptionsAgents
cd OptionsAgents

# 2. activate Python 3.11 (pyenv example)
pyenv install 3.11.9           # once, if not present
pyenv virtualenv 3.11.9 oa-env
pyenv local oa-env             # auto-activates in this folder

# 3. install libs
pip install --upgrade pip
pip install pandas pyarrow duckdb polygon-api-client python-dotenv pytest

# 4. secrets
cp .env.example .env           # then edit .env and paste your POLYGON_KEY

Note: .env is git-ignored; .env.example stays in the repo as documentation.

⸻

One-shot Ingest / Smoke Test

python src/ingest/snapshot.py
# -> "Wrote N rows → data/parquet/spx/date=YYYY-MM-DD/HH_MM_SS.parquet"

duckdb -c "SELECT COUNT(*) FROM parquet_scan('data/parquet/spx/date=*/*.parquet');"
# -> returns non-zero row count


⸻

Automated Tests

pytest -q
# ..   (2 tests should pass)

tests/test_snapshot.py
	•	verifies a Parquet file is written
	•	verifies DuckDB can read a fixture Parquet

⸻

Continuous Integration (add when ready)

.github/workflows/ci.yml

name: CI
on: [push, pull_request]
jobs:
  tests:
    runs-on: macos-14
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: {python-version: '3.11'}
      - run: pip install pandas pyarrow duckdb pytest
      - run: pytest -q

Every push runs the same two tests on a clean macOS runner.

⸻

Next Milestones

Phase	Objective
2 – Ingestion loop	Schedule snapshot.py to run every minute during market hours (launchd or cron).
3 – Analytics view	Create DuckDB views (spx_chain, later spy_chain) over the Parquet folder; extend tests to assert the view row-count > 0.
4 – Deterministic tools	Implement implied_move_calc, dealer_gamma_snapshot, etc., with unit tests.
5 – Planner agent (advisory)	Introduce a function-calling LLM that uses those tools to propose a daily iron-condor; human approval only.
6 – Risk / execution layers	Add risk-guard agent, then paper-trade execution, then live micro-size.


⸻

Quick Commands Reference

# pull one new snapshot manually
python src/ingest/snapshot.py

# run all unit tests
pytest -q

# interactive SQL on all Parquet files
duckdb
.duckdb> SELECT strike, bid, ask
         FROM parquet_scan('data/parquet/spx/date=*/*.parquet')
         WHERE delta IS NOT NULL LIMIT 5;


⸻

Happy building!  Each subsequent milestone layers on top of this foundation without changing the storage layout or test harness.

