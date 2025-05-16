import duckdb, math

def implied_move_calc(db_path="market.duckdb") -> dict:
    conn = duckdb.connect(db_path, read_only=True)

    df = conn.execute("""
      WITH latest AS (               -- most-recent snapshot file
        SELECT *
        FROM   spx_chain
        WHERE  filename = (
                 SELECT filename
                 FROM   spx_chain
                 ORDER  BY date DESC, ts DESC
                 LIMIT 1)
        AND    bid IS NOT NULL        -- ← NEW: only keep quoted rows
        AND    ask IS NOT NULL
      ),
      atm_strike AS (                 -- strike nearest to spot
        SELECT strike
        FROM   latest
        ORDER  BY ABS(strike - (SELECT under_px FROM latest LIMIT 1))
        LIMIT 1
      )
      SELECT
        (SELECT strike FROM atm_strike)                          AS atm,
        AVG((bid+ask)/2) FILTER (WHERE type='C')                 AS c_mid,
        AVG((bid+ask)/2) FILTER (WHERE type='P')                 AS p_mid,
        ANY_VALUE(under_px)                                      AS spot
      FROM latest
      WHERE strike = (SELECT strike FROM atm_strike);
    """).fetchone()

    atm, c_mid, p_mid, spot = df

    # Guard: if either mid is still NULL, treat snapshot as incomplete
    if c_mid is None or p_mid is None or spot is None:
        raise RuntimeError("ATM call or put has NULL quote – snapshot incomplete")

    sigma = c_mid + p_mid
    return {
        "sigma_pts_spx": sigma,
        "sigma_pct":     sigma / spot,
        "sigma_pts_spy": sigma / 10,
    }