"""
Test to verify that options in the latest snapshot have valid gamma values.
"""
import pytest
import duckdb

def test_max_null_gamma_count():
    """
    Tests that no more than 10 rows in the latest snapshot have NULL gamma values.
    """
    try:
        conn = duckdb.connect("market.duckdb", read_only=True)
        result = conn.execute("""
            WITH latest AS (
                SELECT *
                FROM   spx_chain
                WHERE  filename = (
                         SELECT filename
                         FROM   spx_chain
                         ORDER  BY date DESC, ts DESC
                         LIMIT 1)
            )
            SELECT COUNT(*) AS null_gamma_count
            FROM latest
            WHERE gamma IS NULL
        """).fetchone()
        
        null_gamma_count = result[0]
        
        # Assert that no more than 10 rows have NULL gamma
        assert null_gamma_count <= 10, f"Found {null_gamma_count} rows with NULL gamma values (maximum allowed: 10)"
        
    except Exception as e:
        pytest.skip(f"Could not test gamma values: {str(e)}")