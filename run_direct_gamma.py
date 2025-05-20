#!/usr/bin/env python
"""
Run dealer gamma calculation using direct file access and display the results.
"""
import argparse
from src.tools.dealer_gamma_direct import dealer_gamma_snapshot


def format_value(value, formatter):
    """Format a value or return 'N/A' if it's None."""
    if value is None:
        return "N/A"
    return formatter(value)


def run_dealer_gamma(verbose=False):
    """Run dealer gamma calculation and print results."""
    try:
        result = dealer_gamma_snapshot()
        
        print("=== Dealer Gamma Snapshot ===")
        print(f"Total Dealer Gamma: {format_value(result['gamma_total'], lambda x: f'${x:,.0f}')}")
        print(f"Gamma Flip Level: {format_value(result['gamma_flip'], lambda x: f'{x:,.2f}')}")
        
        # Debug info
        print(f"\nFound {len(result['df'])} strikes with gamma values")
        
        if verbose and "df" in result and not result["df"].empty:
            print("\nTop 5 strikes by gamma magnitude:")
            # Get absolute gamma values for sorting
            df = result["df"].copy()
            df["abs_gamma"] = df["dealer_gamma"].abs()
            top_strikes = df.nlargest(5, "abs_gamma")
            
            for _, row in top_strikes.iterrows():
                sign = "+" if row["dealer_gamma"] > 0 else "-"
                print(f"  Strike {row['strike']:,.0f}: {sign}${abs(row['dealer_gamma']):,.0f}")
                
            print("\nDealer Gamma Profile:")
            print(f"  Number of Strikes: {len(df)}")
            print(f"  Mean Gamma per Strike: ${df['dealer_gamma'].mean():,.0f}")
            print(f"  Max Positive Gamma: ${df['dealer_gamma'].max():,.0f}")
            print(f"  Max Negative Gamma: ${df['dealer_gamma'].min():,.0f}")
            
    except Exception as e:
        print(f"Error: {e}")
        return False
        
    return True


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run dealer gamma calculation")
    parser.add_argument("-v", "--verbose", action="store_true", help="Show detailed output")
    args = parser.parse_args()
    
    success = run_dealer_gamma(args.verbose)
    exit(0 if success else 1)