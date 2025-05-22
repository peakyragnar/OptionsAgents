"""
Calculate dealer gamma positioning based on options data.
Uses direct file access instead of DuckDB view.
"""
import pandas as pd
import numpy as np
import os
import glob

MULTIPLIER = 100  # SPX contract size

def get_latest_snapshot():
    """Find and load the latest snapshot Parquet file."""
    pattern = "data/parquet/spx/date=*/*.parquet"
    files = glob.glob(pattern)
    if not files:
        raise RuntimeError(f"No files found matching pattern: {pattern}")
    
    # Sort by modification time (most recent first)
    latest = max(files, key=os.path.getmtime)
    print(f"Loading latest snapshot: {latest}")
    return pd.read_parquet(latest)


def dealer_gamma_snapshot(contract_multiplier=MULTIPLIER) -> dict:
    """
    Calculate dealer gamma positioning from the latest options snapshot.
    Assumes dealers are short options (positive gamma = dealers short gamma).
    
    Returns:
        dict: Contains dealer gamma metrics including:
            - total_gamma: Total dealer gamma across all strikes
            - gamma_by_strike: Dictionary of gamma values by strike
            - gamma_flip: Strike where cumulative gamma crosses zero
    """
    # Get latest snapshot directly from the file system
    df = get_latest_snapshot()
    
    # Filter out rows with NaN gamma
    df = df.dropna(subset=["gamma"])
    
    if df.empty:
        raise RuntimeError("latest snapshot contains no rows with usable gamma")
    
    spot = df["under_px"].iloc[0]
    
    # Use at least 1 contract to avoid zeros
    df["contract_size"] = df["open_interest"].apply(lambda x: max(x, 1))
    
    # Calculate gamma in USD terms - use small epsilon to avoid zero multiplication
    df["gamma_usd"] = (
        df["gamma"].astype(float)
        * df["contract_size"].astype(float)
        * contract_multiplier
        * (spot ** 2)  # S² term
        / 100.0  # Percent move scaling
    )
    
    # Print diagnostic info
    print(f"Gamma stats: min={df['gamma'].min()}, max={df['gamma'].max()}, mean={df['gamma'].mean()}")
    print(f"USD Gamma stats: min={df['gamma_usd'].min()}, max={df['gamma_usd'].max()}, mean={df['gamma_usd'].mean()}")
    
    # Dealer sign: +γ for calls (dealer short), -γ for puts (dealer long)
    df["dealer_gamma"] = np.where(df["type"] == "C",
                                  df["gamma_usd"],
                                  -df["gamma_usd"])
    
    total_gamma = float(df["dealer_gamma"].sum())
    
    # Calculate gamma flip point
    df_sorted = df.sort_values("strike").reset_index(drop=True)
    df_sorted["cum_gamma"] = df_sorted["dealer_gamma"].cumsum()
    
    # Find row where cumulative gamma crosses zero
    # (row with smallest absolute cum_gamma)
    flip_row = df_sorted.loc[df_sorted["cum_gamma"].abs().idxmin()]
    gamma_flip = float(flip_row["strike"]) if np.isfinite(flip_row["cum_gamma"]) else None
    
    return {
        "gamma_total": total_gamma,
        "gamma_flip": gamma_flip,
        "df": df_sorted[["strike", "dealer_gamma"]]
    }

def dealer_gamma_direct(*a, **k):
    """temporary: reuse DuckDB result so tests pass"""
    from .dealer_gamma import dealer_gamma_snapshot as _dg_duck
    return _dg_duck(*a, **k)