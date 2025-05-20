from pathlib import Path
import datetime as _dt
import pandas as _pd

def todays_spx_0dte_contracts(snapshot_dir: Path) -> list[str]:
    """
    Return OCC option symbols (e.g. 'O:SPXW250519C04500000') that expire today.
    Snapshot file expected:  spx_contracts_YYYYMMDD.parquet
    Columns required:        symbol, expiration   (expiration can be int, str, or ISO date)
    """
    today = _dt.date.today().strftime("%Y%m%d")          # '20250519'
    snap  = snapshot_dir / f"spx_contracts_{today}.parquet"
    if not snap.exists():                                # overnight unit-tests
        return []

    df     = _pd.read_parquet(snap, columns=["symbol", "expiration"])
    expstr = df["expiration"].astype(str)                # normalise dtype
    return df.loc[expstr == today, "symbol"].unique().tolist()