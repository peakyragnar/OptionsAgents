import duckdb, datetime as dt, math
from src.utils.greeks import bs_greeks

EPS, TOL = 1e-10, 0.05

def test_greeks_match_black_scholes():
    conn = duckdb.connect("market.duckdb", read_only=True)

    # --- TEMP view ensures vega/theta columns are present --------------
    conn.execute("""
    CREATE OR REPLACE TEMP VIEW spx_chain AS
    SELECT *, substr(filename,-16,8) AS ts
    FROM parquet_scan(
          'data/parquet/spx/date=*/*.parquet',
          filename=true,
          union_by_name=true,
          hive_partitioning=true);
    """)
    # -------------------------------------------------------------------

    rows = conn.execute("""
        SELECT type, strike, under_px AS spot, iv, expiry,
               gamma, vega, theta
        FROM spx_chain
        WHERE filename = (
              SELECT filename FROM spx_chain ORDER BY date DESC, ts DESC LIMIT 1)
        ORDER BY ABS(strike-spot)
        LIMIT 20;
    """).fetchdf().to_dict("records")

    for r in rows:
        if r["iv"] is None:
            continue

        exp = dt.date.fromisoformat(r["expiry"])
        tau = max((exp - dt.date.today()).days, 1) / 365
        theo_γ, theo_ν, theo_θ = bs_greeks(
            r["spot"], r["strike"], r["iv"], tau, r["type"]
        )
        for lbl, theo_val, stored_val in [
            ("gamma", theo_γ, r["gamma"]),
            ("vega",  theo_ν, r["vega"]),
            ("theta", theo_θ, r["theta"]),
        ]:
            if any(math.isnan(x) for x in (theo_val, stored_val)):
                continue
            if abs(theo_val) < EPS and abs(stored_val) < EPS:
                continue
            rel_err = abs(theo_val - stored_val) / max(abs(theo_val), EPS)
            assert rel_err < TOL, f"{lbl} mismatch at K={r['strike']}"