"""
Visualize dealer gamma positioning from intraday snapshots.
"""
import os
import pandas as pd
import matplotlib.pyplot as plt
import pathlib
import glob
import argparse
import datetime as dt

def load_latest_snapshot(path="data/intraday"):
    """Load the latest snapshot file."""
    directory = pathlib.Path(path)
    if not directory.exists():
        raise FileNotFoundError(f"Directory {path} not found")
        
    # Get list of parquet files
    files = glob.glob(str(directory / "*.parquet"))
    if not files:
        raise FileNotFoundError(f"No parquet files found in {path}")
        
    # Sort by modification time (newest first)
    latest_file = max(files, key=os.path.getmtime)
    print(f"Loading latest snapshot: {latest_file}")
    
    return pd.read_parquet(latest_file)

def plot_gamma_profile(df):
    """Plot dealer gamma profile by strike."""
    # Create figure and axis
    fig, ax = plt.subplots(figsize=(12, 8))
    
    # Plot gamma by strike for calls and puts
    calls = df[df['type'] == 'C']
    puts = df[df['type'] == 'P']
    
    # Plot bars
    ax.bar(calls['strike'], calls['gamma_usd'], color='green', alpha=0.7, label='Calls')
    ax.bar(puts['strike'], puts['gamma_usd'], color='red', alpha=0.7, label='Puts')
    
    # Add total line
    total_by_strike = df.groupby('strike')['gamma_usd'].sum().reset_index()
    ax.plot(total_by_strike['strike'], total_by_strike['gamma_usd'], 
            color='blue', linewidth=2, label='Net Gamma')
    
    # Add horizontal line at zero
    ax.axhline(y=0, color='black', linestyle='-', alpha=0.3)
    
    # Set labels and title
    timestamp = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
    ax.set_title(f'Dealer Gamma Exposure Profile ({timestamp})', fontsize=16)
    ax.set_xlabel('Strike Price', fontsize=14)
    ax.set_ylabel('Gamma Exposure ($k per 1% move)', fontsize=14)
    
    # Add summary stats in text box
    total_gamma = df['gamma_usd'].sum()
    props = dict(boxstyle='round', facecolor='wheat', alpha=0.5)
    textstr = f'Total Gamma: ${total_gamma:.2f}k\n'
    textstr += f'Calls: ${calls["gamma_usd"].sum():.2f}k\n'
    textstr += f'Puts: ${puts["gamma_usd"].sum():.2f}k'
    ax.text(0.05, 0.95, textstr, transform=ax.transAxes, fontsize=12,
            verticalalignment='top', bbox=props)
    
    # Add legend
    ax.legend(fontsize=12)
    
    # Add grid
    ax.grid(True, linestyle='--', alpha=0.7)
    
    # Adjust layout
    plt.tight_layout()
    
    return fig

def main():
    """Main function for command line use."""
    parser = argparse.ArgumentParser(description="Visualize dealer gamma profiles")
    parser.add_argument("--path", default="data/intraday", 
                        help="Path to intraday snapshot directory")
    parser.add_argument("--output", default=None,
                        help="Output path for the plot (default: display only)")
    args = parser.parse_args()
    
    try:
        # Load latest data
        df = load_latest_snapshot(args.path)
        
        # Create plot
        fig = plot_gamma_profile(df)
        
        # Save or display
        if args.output:
            fig.savefig(args.output, dpi=300, bbox_inches='tight')
            print(f"Plot saved to {args.output}")
        else:
            plt.show()
            
    except Exception as e:
        print(f"Error: {e}")
        return 1
        
    return 0

if __name__ == "__main__":
    exit(main())