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
import duckdb, pandas as pd, numpy as np

MULTIPLIER = 100  # SPX contract size


def dealer_gamma_snapshot(db_path: str = "market.duckdb",
                          contract_multiplier: int = MULTIPLIER) -> dict:
    conn = duckdb.connect(db_path, read_only=True)

    # --- pull the latest snapshot -------------------------------------------------
    df: pd.DataFrame = conn.execute(
        """
        WITH latest AS (
          SELECT *
          FROM   spx_chain
          WHERE  filename = (
                   SELECT filename
                   FROM   spx_chain
                   ORDER  BY date DESC, ts DESC
                   LIMIT 1)
          AND    gamma IS NOT NULL      -- Filter out NaN gamma
        )
        SELECT strike, type, gamma, open_interest, under_px
        FROM   latest;
        """
    ).fetchdf()

    if df.empty:
        raise RuntimeError("latest snapshot contains no rows with usable gamma and OI")

    spot = df["under_px"].iat[0]

    # --- contract γ → $-γ ----------------------------------------------------------
    # Use at least 1 contract to avoid zeros
    df["contract_size"] = df["open_interest"].apply(lambda x: max(x, 1))
    
    df["gamma_usd"] = (
        df["gamma"].astype(float)
        * df["contract_size"].astype(float)
        * contract_multiplier
        * (spot ** 2)  # S² term
        / 100.0
    )

    # dealer sign: +γ for calls (dealer short) , –γ for puts (dealer long)
    df["dealer_gamma"] = np.where(df["type"] == "C",
                                  df["gamma_usd"],
                                  -df["gamma_usd"])

    total_gamma = float(df["dealer_gamma"].sum())

    # --- flip level: strike where cumulative γ crosses 0 --------------------------
    df_sorted = df.sort_values("strike").reset_index(drop=True)
    df_sorted["cum_gamma"] = df_sorted["dealer_gamma"].cumsum()
    # find row whose |cum_γ| is smallest
    flip_row = df_sorted.loc[df_sorted["cum_gamma"].abs().idxmin()]
    gamma_flip = float(flip_row["strike"]) if np.isfinite(flip_row["cum_gamma"]) else None

    return {
        "gamma_total": total_gamma,
        "gamma_flip":  gamma_flip,
        "df": df_sorted[["strike", "dealer_gamma"]]
    }