"""
Change Detector - Multi-timeframe analysis for detecting spikes, momentum shifts, and trend changes
Critical for catching both gradual buildups and sudden activity jumps
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from collections import deque, defaultdict
from dataclasses import dataclass
import numpy as np

@dataclass
class Change:
    """Detected change event"""
    timestamp: datetime
    change_type: str  # 'SPIKE', 'DIRECTION_FLIP', 'NEW_PIN', 'MOMENTUM_SHIFT'
    strike: Optional[int]
    magnitude: float
    details: Dict
    severity: str  # 'CRITICAL', 'HIGH', 'MEDIUM', 'LOW'

class ChangeDetector:
    """
    Detects significant changes in gamma positioning
    Tracks multiple timeframes to separate noise from real regime changes
    """
    
    def __init__(self):
        # Multi-timeframe tracking
        self.timeframes = {
            '1min': {'window': 60, 'data': defaultdict(lambda: deque(maxlen=60))},
            '5min': {'window': 300, 'data': defaultdict(lambda: deque(maxlen=60))},
            '15min': {'window': 900, 'data': defaultdict(lambda: deque(maxlen=60))}
        }
        
        # Historical data for comparisons
        self.strike_history = defaultdict(list)  # strike -> [(timestamp, volume, gamma)]
        self.net_force_history = deque(maxlen=100)
        self.last_direction = None
        
        # Thresholds
        self.spike_thresholds = {
            'volume': 2.0,      # 2x average
            'gamma': 1.5,       # 50% increase
            'rapid': 3.0        # 3x for rapid detection
        }
        
        # Active alerts
        self.active_alerts = []
        self.detected_changes = deque(maxlen=50)
        
    def update(self, trade, gamma_result, position_tracker):
        """Update with new trade and check for changes"""
        changes = []
        
        # Update strike history
        strike_data = (trade.timestamp, trade.size, gamma_result.total_gamma)
        self.strike_history[trade.strike].append(strike_data)
        
        # Update timeframe data
        for tf_name, tf_config in self.timeframes.items():
            tf_config['data'][trade.strike].append(strike_data)
        
        # Get current market state
        current_state = self._calculate_current_state(position_tracker)
        
        # 1. Check for volume/gamma spikes
        spike_changes = self._detect_spikes(trade, gamma_result)
        changes.extend(spike_changes)
        
        # 2. Check for direction flips
        direction_change = self._detect_direction_flip(current_state)
        if direction_change:
            changes.append(direction_change)
            
        # 3. Check for new pin formation
        new_pins = self._detect_new_pins(position_tracker)
        changes.extend(new_pins)
        
        # 4. Check for momentum shifts
        momentum_changes = self._detect_momentum_shifts(current_state)
        changes.extend(momentum_changes)
        
        # Store detected changes
        for change in changes:
            self.detected_changes.append(change)
            position_tracker.record_change(
                strike=change.strike or 0,
                volume=trade.size,
                gamma_added=gamma_result.total_gamma,
                alert_type=change.change_type,
                details=change.details
            )
            
        return changes
    
    def _detect_spikes(self, trade, gamma_result) -> List[Change]:
        """Detect sudden spikes in volume or gamma"""
        changes = []
        strike = trade.strike
        
        # Get historical averages
        avg_1min = self._get_average_volume(strike, '1min')
        avg_5min = self._get_average_volume(strike, '5min')
        
        if avg_1min > 0:
            volume_ratio = trade.size / avg_1min
            
            # Check for significant spike
            if volume_ratio >= self.spike_thresholds['rapid']:
                severity = 'CRITICAL'
            elif volume_ratio >= self.spike_thresholds['volume']:
                severity = 'HIGH'
            else:
                severity = None
                
            if severity:
                changes.append(Change(
                    timestamp=trade.timestamp,
                    change_type='SPIKE',
                    strike=strike,
                    magnitude=volume_ratio,
                    details={
                        'volume': trade.size,
                        'average_1min': avg_1min,
                        'gamma_added': gamma_result.total_gamma,
                        'option_type': trade.option_type
                    },
                    severity=severity
                ))
                
        return changes
    
    def _detect_direction_flip(self, current_state) -> Optional[Change]:
        """Detect market direction changes"""
        current_direction = current_state['direction']
        
        if self.last_direction and current_direction != self.last_direction:
            # Significant direction change
            change = Change(
                timestamp=datetime.now(),
                change_type='DIRECTION_FLIP',
                strike=None,
                magnitude=abs(current_state['net_force']),
                details={
                    'from': self.last_direction,
                    'to': current_direction,
                    'net_force': current_state['net_force'],
                    'confidence': current_state['confidence']
                },
                severity='CRITICAL'
            )
            self.last_direction = current_direction
            return change
            
        self.last_direction = current_direction
        return None
    
    def _detect_new_pins(self, position_tracker) -> List[Change]:
        """Detect rapidly forming pin levels"""
        changes = []
        
        # Get current top pins
        top_pins = position_tracker.get_top_pins(n=10)
        
        for _, pin in top_pins.iterrows():
            strike = pin['strike']
            current_gamma = pin['total_gamma_force']
            
            # Check historical gamma for this strike
            history = self.strike_history[strike]
            if len(history) >= 5:  # Need some history
                # Get gamma from 5 minutes ago
                five_min_ago = datetime.now() - timedelta(minutes=5)
                old_gamma = sum(h[2] for h in history if h[0] < five_min_ago)
                
                if old_gamma < current_gamma * 0.1:  # Was less than 10% of current
                    growth_rate = current_gamma / max(old_gamma, 1)
                    
                    if growth_rate > 5:  # 5x growth
                        changes.append(Change(
                            timestamp=datetime.now(),
                            change_type='NEW_PIN',
                            strike=strike,
                            magnitude=growth_rate,
                            details={
                                'current_gamma': current_gamma,
                                'growth_rate': growth_rate,
                                'direction': pin['direction']
                            },
                            severity='HIGH'
                        ))
                        
        return changes
    
    def _detect_momentum_shifts(self, current_state) -> List[Change]:
        """Detect acceleration or deceleration in directional moves"""
        changes = []
        
        # Store current net force
        self.net_force_history.append((datetime.now(), current_state['net_force']))
        
        if len(self.net_force_history) >= 10:
            # Calculate momentum over different periods
            now = datetime.now()
            
            # 1-minute momentum
            one_min_ago = now - timedelta(minutes=1)
            recent_forces = [f for t, f in self.net_force_history if t > one_min_ago]
            
            # 5-minute momentum  
            five_min_ago = now - timedelta(minutes=5)
            older_forces = [f for t, f in self.net_force_history if one_min_ago > t > five_min_ago]
            
            if recent_forces and older_forces:
                recent_avg = np.mean(recent_forces)
                older_avg = np.mean(older_forces)
                
                # Check for acceleration
                if abs(recent_avg) > abs(older_avg) * 1.5:
                    changes.append(Change(
                        timestamp=now,
                        change_type='MOMENTUM_SHIFT',
                        strike=None,
                        magnitude=recent_avg / older_avg,
                        details={
                            'type': 'ACCELERATING',
                            'direction': 'UP' if recent_avg > 0 else 'DOWN',
                            'recent_force': recent_avg,
                            'older_force': older_avg
                        },
                        severity='HIGH'
                    ))
                    
        return changes
    
    def _calculate_current_state(self, position_tracker) -> Dict:
        """Calculate current market state"""
        positions = position_tracker.get_all_positions()
        
        if positions.empty:
            return {
                'net_force': 0,
                'direction': 'NEUTRAL',
                'confidence': 0
            }
            
        # Calculate directional forces
        upward = positions[positions['net_gamma'] > 0]['net_gamma'].sum()
        downward = abs(positions[positions['net_gamma'] < 0]['net_gamma'].sum())
        
        net_force = upward - downward
        
        return {
            'net_force': net_force,
            'direction': 'UP' if net_force > 0 else 'DOWN',
            'confidence': min(abs(net_force) / 1000000, 1.0)
        }
    
    def _get_average_volume(self, strike: int, timeframe: str) -> float:
        """Get average volume for a strike over timeframe"""
        data = self.timeframes[timeframe]['data'][strike]
        if not data:
            return 0
            
        volumes = [d[1] for d in data]  # Extract volumes
        return np.mean(volumes) if volumes else 0
    
    def get_active_alerts(self, severity_filter: Optional[str] = None) -> List[Change]:
        """Get currently active alerts"""
        # Filter recent changes (last 5 minutes)
        cutoff = datetime.now() - timedelta(minutes=5)
        active = [c for c in self.detected_changes if c.timestamp > cutoff]
        
        if severity_filter:
            active = [c for c in active if c.severity == severity_filter]
            
        return active
    
    def get_summary(self) -> Dict:
        """Get change detection summary"""
        alerts = self.get_active_alerts()
        
        return {
            'total_alerts': len(alerts),
            'critical_alerts': len([a for a in alerts if a.severity == 'CRITICAL']),
            'high_alerts': len([a for a in alerts if a.severity == 'HIGH']),
            'recent_spikes': [a for a in alerts if a.change_type == 'SPIKE'][:5],
            'direction_flips': [a for a in alerts if a.change_type == 'DIRECTION_FLIP'],
            'new_pins': [a for a in alerts if a.change_type == 'NEW_PIN']
        }