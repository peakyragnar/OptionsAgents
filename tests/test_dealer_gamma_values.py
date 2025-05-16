# tests/test_dealer_gamma_values.py
import duckdb, datetime as dt, math
from src.utils.greeks import bs_greeks   # S, K, iv, tau, cp  -> γ, ν, θ

EPS = 1e-10
TOL = 0.05

def test_gamma_matches_black_scholes():
    conn = duckdb.connect("market.duckdb", read_only=True)

    rows = conn.execute("""
      SELECT
         type,
         strike,
         under_px AS spot,
         iv,
         expiry,
         gamma                    -- ← add this column
      FROM spx_chain
      WHERE filename = (
            SELECT filename
            FROM   spx_chain
            ORDER  BY date DESC, ts DESC
            LIMIT 1)
      ORDER BY ABS(strike-spot)          -- ATM first
      LIMIT 20;
    """).fetchdf().to_dict("records")

    for r in rows:
        if r["iv"] is None:
            continue                     # skip rows with missing IV

        exp = dt.date.fromisoformat(r["expiry"])
        tau = max((exp - dt.date.today()).days, 1) / 365
        theo_γ, _, _ = bs_greeks(r["spot"], r["strike"], r["iv"], tau, r["type"])
        stored = r["gamma"]

        # ── skip rows where either side is NaN ───────────────────────────
        if any(math.isnan(x) for x in (theo_γ, stored)):
            continue
        # ── treat both tiny numbers as zero ──────────────────────────────
        if abs(theo_γ) < EPS and abs(stored) < EPS:
            continue
        # ── relative-error test ──────────────────────────────────────────
        rel_err = abs(theo_γ - stored) / max(abs(theo_γ), EPS)
        assert rel_err < TOL, f"{r['strike']} γ mismatch {rel_err:.2%}"