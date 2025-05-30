"""
Position Tracker - Maintains dealer short positions and gamma exposure by strike
Stores data in DuckDB for real-time queries and Parquet for historical analysis
"""

import duckdb
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from collections import defaultdict
from pathlib import Path
import json
import os

class PositionTracker:
    """
    Tracks cumulative dealer positions and gamma exposure
    Maintains both in-memory state and persistent storage
    """
    
    def __init__(self, db_path: str = 'data/gamma_tool_sam.duckdb'):
        # Ensure data directory exists
        os.makedirs('data', exist_ok=True)
        self.db_path = db_path
        self.conn = duckdb.connect(db_path)
        self.positions = defaultdict(lambda: {
            'call_volume': 0,
            'put_volume': 0,
            'call_gamma': 0.0,
            'put_gamma': 0.0,
            'last_update': None
        })
        
        # Initialize database tables
        self._init_database()
        
        # Archive settings
        self.archive_interval = 300  # 5 minutes
        self.last_archive = datetime.now()
        
    def _init_database(self):
        """Initialize DuckDB tables"""
        
        # Live positions table
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS gamma_positions_live (
                timestamp TIMESTAMP,
                strike INTEGER,
                option_type VARCHAR(4),
                cumulative_volume INTEGER,
                gamma_per_contract REAL,
                total_gamma REAL,
                directional_force VARCHAR(10),
                spx_price REAL,
                PRIMARY KEY (strike, option_type)
            )
        """)
        
        # Changes tracking
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS gamma_changes_1min (
                timestamp TIMESTAMP,
                strike INTEGER,
                volume_spike INTEGER,
                gamma_added REAL,
                alert_type VARCHAR(20),
                details VARCHAR
            )
        """)
        
        # Current analysis state
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS gamma_analysis_current (
                timestamp TIMESTAMP PRIMARY KEY,
                net_force REAL,
                primary_pin INTEGER,
                direction VARCHAR(10),
                confidence REAL,
                top_strikes VARCHAR,
                active_alerts VARCHAR
            )
        """)
        
    def update_position(self, trade, gamma_result):
        """Update position for a trade"""
        strike = trade.strike
        
        # Update in-memory positions
        if trade.option_type == 'CALL':
            self.positions[strike]['call_volume'] += trade.size
            self.positions[strike]['call_gamma'] += gamma_result.total_gamma
        else:
            self.positions[strike]['put_volume'] += trade.size
            self.positions[strike]['put_gamma'] += gamma_result.total_gamma
            
        self.positions[strike]['last_update'] = trade.timestamp
        
        # Update database
        self.conn.execute("""
            INSERT INTO gamma_positions_live 
            (timestamp, strike, option_type, cumulative_volume, gamma_per_contract, 
             total_gamma, directional_force, spx_price)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (strike, option_type) DO UPDATE SET
                timestamp = EXCLUDED.timestamp,
                cumulative_volume = gamma_positions_live.cumulative_volume + ?,
                total_gamma = gamma_positions_live.total_gamma + ?,
                gamma_per_contract = EXCLUDED.gamma_per_contract,
                spx_price = EXCLUDED.spx_price
        """, [
            trade.timestamp, strike, trade.option_type, trade.size,
            gamma_result.gamma_per_contract, gamma_result.total_gamma,
            gamma_result.directional_force, gamma_result.spx_price,
            trade.size, gamma_result.total_gamma
        ])
        
        # Check if we need to archive
        if (datetime.now() - self.last_archive).seconds >= self.archive_interval:
            self.archive_positions()
            
    def get_position_by_strike(self, strike: int) -> Dict:
        """Get current position for a specific strike"""
        return dict(self.positions[strike])
    
    def get_all_positions(self) -> pd.DataFrame:
        """Get all current positions as DataFrame"""
        result = self.conn.execute("""
            SELECT strike, 
                   SUM(CASE WHEN option_type = 'CALL' THEN cumulative_volume ELSE 0 END) as call_volume,
                   SUM(CASE WHEN option_type = 'PUT' THEN cumulative_volume ELSE 0 END) as put_volume,
                   SUM(CASE WHEN option_type = 'CALL' THEN total_gamma ELSE 0 END) as call_gamma,
                   SUM(CASE WHEN option_type = 'PUT' THEN total_gamma ELSE 0 END) as put_gamma,
                   SUM(total_gamma) as net_gamma,
                   MAX(spx_price) as spx_price
            FROM gamma_positions_live
            GROUP BY strike
            ORDER BY strike
        """).df()
        
        return result
    
    def get_top_pins(self, n: int = 5, direction: Optional[str] = None) -> pd.DataFrame:
        """Get top gamma concentration strikes"""
        query = """
            SELECT strike, 
                   SUM(ABS(total_gamma)) as total_gamma_force,
                   MAX(directional_force) as direction,
                   SUM(cumulative_volume) as total_volume
            FROM gamma_positions_live
        """
        
        if direction:
            query += f" WHERE directional_force = '{direction}'"
            
        query += """
            GROUP BY strike
            ORDER BY total_gamma_force DESC
            LIMIT ?
        """
        
        return self.conn.execute(query, [n]).df()
    
    def record_change(self, strike: int, volume: int, gamma_added: float, 
                     alert_type: str, details: Dict):
        """Record significant changes for detection"""
        self.conn.execute("""
            INSERT INTO gamma_changes_1min
            (timestamp, strike, volume_spike, gamma_added, alert_type, details)
            VALUES (?, ?, ?, ?, ?, ?)
        """, [
            datetime.now(), strike, volume, gamma_added, 
            alert_type, json.dumps(details)
        ])
    
    def update_analysis_state(self, analysis: Dict):
        """Update current analysis state"""
        self.conn.execute("""
            INSERT OR REPLACE INTO gamma_analysis_current
            (timestamp, net_force, primary_pin, direction, confidence, 
             top_strikes, active_alerts)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, [
            datetime.now(),
            analysis['net_force'],
            analysis.get('primary_pin', {}).get('strike'),
            analysis['direction'],
            analysis['confidence'],
            json.dumps(analysis.get('top_strikes', [])),
            json.dumps(analysis.get('active_alerts', []))
        ])
    
    def archive_positions(self):
        """Archive current positions to Parquet"""
        # Create archive directory
        date_str = datetime.now().strftime('%Y-%m-%d')
        time_str = datetime.now().strftime('%H_%M_%S')
        archive_dir = Path(f'data/gamma_tool_sam/positions/date={date_str}')
        archive_dir.mkdir(parents=True, exist_ok=True)
        
        # Get current positions
        df = self.get_all_positions()
        if not df.empty:
            # Save to parquet
            archive_path = archive_dir / f'{time_str}.parquet'
            df.to_parquet(archive_path)
            
        self.last_archive = datetime.now()
        
    def get_recent_changes(self, minutes: int = 5) -> pd.DataFrame:
        """Get recent position changes"""
        cutoff = datetime.now() - timedelta(minutes=minutes)
        return self.conn.execute("""
            SELECT * FROM gamma_changes_1min
            WHERE timestamp > ?
            ORDER BY timestamp DESC
        """, [cutoff]).df()