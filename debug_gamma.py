#!/usr/bin/env python
"""
Diagnostic script to debug gamma calculations and understand why we're getting zeros.
"""
import pandas as pd
import numpy as np
import os
import glob
import matplotlib.pyplot as plt
import math

# Constants
MULTIPLIER = 100  # SPX contract size


def find_latest_snapshot():
    """Find the latest snapshot file."""
    pattern = "data/parquet/spx/date=*/*.parquet"
    files = glob.glob(pattern)
    latest_file = max(files, key=os.path.getmtime)
    print(f"Found latest snapshot: {latest_file}")
    return latest_file


def format_number(x):
    """Format a number with commas for thousands."""
    return f"{x:,.6f}" if abs(x) < 0.01 else f"{x:,.4f}"


def inspect_file(file_path):
    """Inspect a Parquet file for gamma and other relevant fields."""
    print(f"\nInspecting file: {file_path}")
    df = pd.read_parquet(file_path)
    
    # Basic stats
    print(f"Rows: {len(df)}")
    print(f"Null counts:")
    for col in ['gamma', 'delta', 'vega', 'theta', 'open_interest', 'volume', 'bid', 'ask']:
        if col in df.columns:
            print(f"  {col}: {df[col].isna().sum()} nulls")
    
    # Show gamma stats
    if 'gamma' in df.columns:
        gamma_stats = df['gamma'].describe()
        print("\nGamma statistics:")
        for stat, value in gamma_stats.items():
            print(f"  {stat}: {format_number(value)}")
        
        # Count zeros
        zero_gamma = (df['gamma'] == 0).sum()
        print(f"  Zero gamma values: {zero_gamma} ({zero_gamma/len(df)*100:.1f}%)")
    
    # Open Interest
    if 'open_interest' in df.columns:
        oi_stats = df['open_interest'].describe()
        print("\nOpen Interest statistics:")
        for stat, value in oi_stats.items():
            print(f"  {stat}: {format_number(value)}")
        
        # Count zeros
        zero_oi = (df['open_interest'] == 0).sum()
        print(f"  Zero OI values: {zero_oi} ({zero_oi/len(df)*100:.1f}%)")
    
    # Calculate USD gamma
    if 'gamma' in df.columns and 'open_interest' in df.columns and 'under_px' in df.columns:
        print("\nRecalculating gamma USD values:")
        
        # Get spot price
        spot = df['under_px'].iloc[0]
        print(f"  Spot price: {format_number(spot)}")
        
        # Use max(oi, 1) to avoid zeros
        df['oi_safe'] = df['open_interest'].apply(lambda x: max(float(x), 1.0))
        
        # Calculate gamma in USD terms
        df['gamma_usd'] = (
            df['gamma'].astype(float) *
            df['oi_safe'].astype(float) *
            MULTIPLIER *
            (spot ** 2) / 100.0
        )
        
        # Print stats
        gamma_usd_stats = df['gamma_usd'].describe()
        print("\nGamma USD statistics:")
        for stat, value in gamma_usd_stats.items():
            print(f"  {stat}: {format_number(value)}")
        
        # Sum by type
        call_gamma = df.loc[df['type'] == 'C', 'gamma_usd'].sum()
        put_gamma = df.loc[df['type'] == 'P', 'gamma_usd'].sum()
        total_gamma = call_gamma - put_gamma  # Dealers: short calls, long puts
        
        print(f"\nDealer gamma components:")
        print(f"  Call gamma (dealer short): +${call_gamma:,.0f}")
        print(f"  Put gamma (dealer long): -${put_gamma:,.0f}")
        print(f"  Total dealer gamma: ${total_gamma:,.0f}")
        
        # Sample data (top 5 by absolute gamma)
        df['abs_gamma_usd'] = df['gamma_usd'].abs()
        top_gamma = df.nlargest(5, 'abs_gamma_usd')
        
        print("\nTop 5 options by gamma magnitude:")
        for _, row in top_gamma.iterrows():
            sign = "+" if row['type'] == 'C' else "-"
            print(f"  Strike {row['strike']:.0f} {row['type']}: gamma={row['gamma']:.6f}, "
                  f"OI={row['open_interest']:.0f}, "
                  f"USD={sign}${abs(row['gamma_usd']):.0f}")
        
        return df
    
    return None


if __name__ == "__main__":
    # Find and inspect the latest snapshot
    latest_file = find_latest_snapshot()
    result_df = inspect_file(latest_file)
    
    # If we found data, plot it
    if result_df is not None and 'strike' in result_df.columns and 'gamma_usd' in result_df.columns:
        # Create a simple gamma profile plot
        plt.figure(figsize=(12, 6))
        
        # Calls (positive for dealer)
        calls = result_df[result_df['type'] == 'C']
        plt.scatter(calls['strike'], calls['gamma_usd'], 
                   label='Calls (Dealer Short)', color='green', alpha=0.5)
        
        # Puts (negative for dealer)
        puts = result_df[result_df['type'] == 'P']
        plt.scatter(puts['strike'], -puts['gamma_usd'], 
                   label='Puts (Dealer Long)', color='red', alpha=0.5)
        
        plt.axhline(y=0, color='black', linestyle='-', alpha=0.3)
        plt.grid(True, alpha=0.3)
        plt.title('Dealer Gamma Profile by Strike')
        plt.xlabel('Strike Price')
        plt.ylabel('Dealer Gamma ($)')
        plt.legend()
        
        # Save the plot
        plt.savefig('dealer_gamma_profile.png')
        print(f"\nGamma profile plot saved to dealer_gamma_profile.png")
    else:
        print("\nCouldn't generate gamma profile plot due to missing data.")