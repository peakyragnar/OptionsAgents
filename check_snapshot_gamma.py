#!/usr/bin/env python
"""Check gamma values in snapshot database"""
import duckdb

con = duckdb.connect("market.duckdb", read_only=True)

# Check gamma values
gamma_check = con.execute("""
    SELECT COUNT(*) as total,
           COUNT(gamma) as has_gamma,
           COUNT(CASE WHEN gamma != 0 THEN 1 END) as non_zero_gamma
    FROM spx_chain
    WHERE filename = (SELECT filename FROM spx_chain ORDER BY date DESC, ts DESC LIMIT 1)
""").fetchone()

print(f"Latest snapshot gamma stats:")
print(f"  Total rows: {gamma_check[0]}")
print(f"  Has gamma: {gamma_check[1]}")  
print(f"  Non-zero gamma: {gamma_check[2]}")

# Sample some gamma values
sample = con.execute("""
    SELECT strike, gamma, open_interest, under_px
    FROM spx_chain  
    WHERE filename = (SELECT filename FROM spx_chain ORDER BY date DESC, ts DESC LIMIT 1)
    AND gamma IS NOT NULL
    LIMIT 5
""").fetchall()

print(f"\nSample gamma values:")
for row in sample:
    print(f"  Strike {row[0]}: gamma={row[1]}, OI={row[2]}, SPX={row[3]}")

con.close()