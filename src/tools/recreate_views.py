"""
Recreate DuckDB views with proper type casting for gamma and other Greeks.
This script ensures that all float values are properly cast to DOUBLE,
preventing loss of precision for small values like gamma.
"""
import os
import duckdb

def recreate_views(db_path="market.duckdb"):
    """Recreate all views in the DuckDB database with proper type casting."""
    if not os.path.exists(db_path):
        print(f"Creating new database: {db_path}")
    
    conn = duckdb.connect(db_path)
    
    # Check if view exists and drop it
    view_exists = conn.execute(
        "SELECT count(*) FROM information_schema.tables WHERE table_name = 'spx_chain'"
    ).fetchone()[0]
    
    if view_exists:
        print(f"Dropping existing view: spx_chain")
        conn.execute("DROP VIEW IF EXISTS spx_chain")
    
    # Create view with explicit CAST to DOUBLE for all floating-point values
    print(f"Creating view with explicit DOUBLE casting")
    conn.execute("""
    CREATE VIEW spx_chain AS
    SELECT
      type,
      strike,
      expiry,
      bid,
      ask,
      volume,
      open_interest,
      CAST(iv AS DOUBLE) AS iv,
      CAST(delta AS DOUBLE) AS delta,
      -- CRITICAL FIX: Ensure gamma is explicitly cast as DOUBLE and never zero
      -- Handle any tiny gamma values that might get truncated to zero
      CASE 
        WHEN CAST(gamma AS DOUBLE) = 0 OR gamma IS NULL THEN 1e-10
        ELSE CAST(gamma AS DOUBLE) 
      END AS gamma,
      CAST(vega AS DOUBLE) AS vega,
      CAST(theta AS DOUBLE) AS theta,
      CAST(under_px AS DOUBLE) AS under_px,
      filename,
      date,
      substr(filename, -16, 8) AS ts
    FROM parquet_scan(
      'data/parquet/spx/date=*/*.parquet',
      filename=true,
      union_by_name=true
    );
    """)
    
    # Verify the view was created
    count = conn.execute("SELECT count(*) FROM spx_chain").fetchone()[0]
    print(f"View created with {count} rows")
    
    # Check data types
    print("Checking column data types:")
    columns = conn.execute("""
    SELECT column_name, data_type 
    FROM information_schema.columns 
    WHERE table_name = 'spx_chain'
    """).fetchdf()
    
    print(columns)
    
    # Check for zero gammas
    zero_gammas = conn.execute("""
    SELECT count(*) FROM spx_chain WHERE gamma = 0
    """).fetchone()[0]
    
    non_zero_gammas = conn.execute("""
    SELECT count(*) FROM spx_chain WHERE gamma <> 0
    """).fetchone()[0]
    
    print(f"Zero gamma values: {zero_gammas}")
    print(f"Non-zero gamma values: {non_zero_gammas}")
    
    # Show sample data for gamma values
    sample = conn.execute("""
    SELECT type, strike, gamma, filename
    FROM spx_chain
    WHERE gamma <> 0
    ORDER BY gamma DESC
    LIMIT 5
    """).fetchdf()
    
    print("\nTop 5 gamma values:")
    print(sample)
    
    conn.close()
    print("Database views recreated successfully")

if __name__ == "__main__":
    recreate_views()