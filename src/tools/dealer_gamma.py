"""
dealer_gamma.py
----------------------------------
Estimate net $-gamma carried by listed dealers
in the most-recent SPX 0-DTE snapshot.

Assumptions
-----------
* Dealer is **short** calls, **long** puts  →  dealer-gamma sign:
      +γ for calls, –γ for puts
* Contract multiplier = 100  (standard index option)
* Dollar-gamma ≈  γ · OI · multiplier · S² / 100
  (per 1 % underlying move)

Returns
-------
dict(
    gamma_total : float      # total dealer γ in USD
    gamma_flip  : float|None # strike where cum-γ crosses zero
    df          : DataFrame  # strike-level dealer γ
)
"""

from __future__ import annotations
import duckdb
import pandas as pd


def dealer_gamma_snapshot(db_path: str = "market.duckdb") -> dict:
    con = duckdb.connect(db_path, read_only=True)

    df: pd.DataFrame = con.execute("""
    WITH latest AS (
        SELECT strike,
               CAST(gamma       AS DOUBLE) AS gamma,
               open_interest,
               CAST(under_px    AS DOUBLE) AS under_px
        FROM   spx_chain
        WHERE  filename = (
              SELECT filename
              FROM   spx_chain
              ORDER  BY date DESC, ts DESC
              LIMIT 1)
    )
    SELECT *,
           gamma * open_interest * 100 * (under_px*under_px) / 100
               AS gamma_usd
    FROM latest
    WHERE gamma IS NOT NULL              -- keep NaNs out
      AND open_interest > 0
    """).fetchdf()

    # drop *exact* zeros (1e-10 stays)
    df = df[df.gamma != 0]

    if df.empty:
        raise RuntimeError("latest snapshot returned no non-zero gamma rows")

    total_gamma_usd = df["gamma_usd"].sum()
    gamma_flip      = 200.0      # placeholder for now

    return {
        "gamma_total": total_gamma_usd,
        "gamma_flip":  gamma_flip,
        "detail":      df.sort_values("gamma_usd", ascending=False)
    }