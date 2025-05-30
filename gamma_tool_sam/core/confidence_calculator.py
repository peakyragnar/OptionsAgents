"""
Sophisticated Confidence Calculator for Gamma Tool Sam
Multi-factor confidence scoring with market adaptation
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
import json
from collections import deque
import numpy as np

@dataclass
class MarketConditions:
    """Current market conditions affecting confidence"""
    time: str  # HH:MM format
    vix: float = 15.0
    volume_percentile: float = 50.0  # 0-100
    days_to_expiry: int = 0
    
@dataclass
class ConfidenceComponents:
    """Breakdown of confidence calculation"""
    force_score: float
    imbalance_score: float
    concentration_score: float
    distance_score: float
    momentum_score: float
    quality_score: float
    pattern_adjustment: float
    
class ConfidenceCalculator:
    """
    Sophisticated multi-factor confidence calculation
    Adapts to market conditions and learns from outcomes
    """
    
    def __init__(self):
        # Historical tracking for calibration
        self.prediction_history = deque(maxlen=1000)
        
        # Pattern definitions
        self.patterns = {
            'pin_sandwich': self._detect_pin_sandwich,
            'near_gamma_flip': self._detect_gamma_flip,
            'competing_pins': self._detect_competing_pins,
            'momentum_divergence': self._detect_momentum_divergence,
            'volume_surge': self._detect_volume_surge
        }
        
        # Component weights (can be adjusted based on performance)
        self.weights = {
            'force': 0.30,      # Raw gamma force magnitude
            'imbalance': 0.25,  # Directional imbalance
            'concentration': 0.20,  # Pin concentration
            'distance': 0.15,   # Distance to primary pin
            'momentum': 0.10    # Recent momentum alignment
        }
        
    def calculate_confidence(self, analysis_data: Dict, market_conditions: Optional[MarketConditions] = None) -> Tuple[float, Dict]:
        """
        Calculate sophisticated confidence with full breakdown
        """
        if not market_conditions:
            market_conditions = self._get_current_conditions()
            
        # Calculate all components
        components = self._calculate_components(analysis_data, market_conditions)
        
        # Get base confidence from weighted combination
        base_confidence = self._combine_components(components)
        
        # Detect and adjust for patterns
        detected_patterns = self._detect_patterns(analysis_data)
        pattern_adjusted = self._adjust_for_patterns(base_confidence, detected_patterns)
        
        # Apply gamma quality scoring
        quality_adjusted = self._apply_quality_score(pattern_adjusted, analysis_data)
        
        # Dynamic threshold adjustment
        threshold_adjusted = self._apply_dynamic_threshold(quality_adjusted, market_conditions)
        
        # Final calibration from historical performance
        final_confidence = self._calibrate_from_history(threshold_adjusted, analysis_data)
        
        # Generate explanation
        explanation = self._generate_explanation(components, detected_patterns, final_confidence)
        
        return final_confidence, {
            'components': components.__dict__,
            'patterns': detected_patterns,
            'explanation': explanation,
            'market_conditions': market_conditions.__dict__,
            'adjustments': {
                'base': base_confidence,
                'pattern_adjusted': pattern_adjusted,
                'quality_adjusted': quality_adjusted,
                'final': final_confidence
            }
        }
        
    def _calculate_components(self, data: Dict, conditions: MarketConditions) -> ConfidenceComponents:
        """Calculate all confidence components"""
        
        # 1. Force Score - Magnitude of net directional force
        net_force = abs(data.get('net_force', 0))
        force_score = min(net_force / self._get_force_threshold(conditions), 1.0)
        
        # 2. Imbalance Score - How one-sided is the gamma?
        up = data.get('upward_force', 0)
        down = data.get('downward_force', 0)
        total = up + down
        if total > 0:
            imbalance_score = abs(up - down) / total
        else:
            imbalance_score = 0
            
        # 3. Concentration Score - Gamma concentrated or spread out?
        concentration_score = self._calculate_concentration(data)
        
        # 4. Distance Score - How far is primary pin from current price?
        distance_score = self._calculate_distance_score(data)
        
        # 5. Momentum Score - Recent activity alignment
        momentum_score = self._calculate_momentum_score(data)
        
        # 6. Quality Score - Gamma quality assessment
        quality_score = self._calculate_gamma_quality(data)
        
        return ConfidenceComponents(
            force_score=force_score,
            imbalance_score=imbalance_score,
            concentration_score=concentration_score,
            distance_score=distance_score,
            momentum_score=momentum_score,
            quality_score=quality_score,
            pattern_adjustment=1.0  # Applied later
        )
        
    def _get_force_threshold(self, conditions: MarketConditions) -> float:
        """Dynamic threshold based on market conditions - matches gamma_engine thresholds"""
        # Get time in minutes since midnight
        hour = int(conditions.time.split(':')[0])
        minute = int(conditions.time.split(':')[1])
        time_minutes = hour * 60 + minute
        
        # Base thresholds matching gamma_engine
        if time_minutes < 600:  # Before 10:00 AM (9:30-10:00)
            base_threshold = 25000  # Very low threshold - morning positioning
        elif time_minutes < 660:  # 10:00-11:00 AM
            base_threshold = 75000  # Building positions
        elif time_minutes < 840:  # 11:00 AM - 2:00 PM
            base_threshold = 150000  # Peak trading hours
        elif time_minutes < 930:  # 2:00-3:30 PM
            base_threshold = 250000  # Heavy positioning
        else:  # 3:30-4:00 PM
            base_threshold = 400000  # End of day - massive gamma needed
            
        # Volatility adjustment (more subtle than before)
        if conditions.vix > 20:
            vix_multiplier = 1.2  # Reduced from 1.3
        elif conditions.vix < 12:
            vix_multiplier = 0.9  # Reduced from 0.8
        else:
            vix_multiplier = 1.0
            
        # Volume adjustment (more subtle)
        if conditions.volume_percentile > 80:
            volume_multiplier = 0.95  # High volume = slightly more significant
        elif conditions.volume_percentile < 20:
            volume_multiplier = 1.1  # Low volume = need slightly more conviction
        else:
            volume_multiplier = 1.0
            
        return base_threshold * vix_multiplier * volume_multiplier
        
    def _calculate_concentration(self, data: Dict) -> float:
        """Calculate how concentrated gamma is at top strikes"""
        all_pins = data.get('all_pins', [])
        if not all_pins:
            return 0
            
        # Get top 3 pins
        top_pins = sorted(all_pins, key=lambda x: x.get('force', 0), reverse=True)[:3]
        
        if not top_pins:
            return 0
            
        top_gamma = sum(pin.get('force', 0) for pin in top_pins)
        total_gamma = sum(pin.get('force', 0) for pin in all_pins)
        
        return top_gamma / total_gamma if total_gamma > 0 else 0
        
    def _calculate_distance_score(self, data: Dict) -> float:
        """Score based on distance to primary pin"""
        primary_pin = data.get('primary_pin')
        spx_price = data.get('spx_price')
        
        if not primary_pin or not spx_price:
            return 0
            
        distance = abs(primary_pin['strike'] - spx_price)
        
        # Score decreases with distance (50 points = 0 score)
        return max(0, 1 - (distance / 50))
        
    def _calculate_momentum_score(self, data: Dict) -> float:
        """Score based on recent momentum alignment"""
        alerts = data.get('active_alerts', [])
        direction = data.get('direction', 'NEUTRAL')
        
        # Check for momentum shifts in same direction
        aligned_alerts = 0
        opposing_alerts = 0
        
        for alert in alerts:
            # Handle both dict and Change object
            if hasattr(alert, 'change_type'):
                alert_type = alert.change_type
                alert_details = alert.details
            else:
                alert_type = alert.get('type')
                alert_details = alert.get('details', {})
                
            if alert_type == 'MOMENTUM_SHIFT':
                if alert_details.get('direction') == direction:
                    aligned_alerts += 1
                else:
                    opposing_alerts += 1
                    
        if aligned_alerts > opposing_alerts:
            return 0.9
        elif opposing_alerts > aligned_alerts:
            return 0.3
        else:
            return 0.6
            
    def _calculate_gamma_quality(self, data: Dict) -> float:
        """Assess quality of gamma (volume-backed, recent, etc)"""
        primary_pin = data.get('primary_pin', {})
        alerts = data.get('active_alerts', [])
        
        quality_factors = {
            'volume_backed': 0.4,
            'recent': 0.3,
            'institutional': 0.2,
            'persistent': 0.1
        }
        
        scores = {}
        
        # Volume backed - check if pin has volume
        if primary_pin.get('volume', 0) > 100:
            scores['volume_backed'] = 1.0
        elif primary_pin.get('volume', 0) > 50:
            scores['volume_backed'] = 0.7
        else:
            scores['volume_backed'] = 0.3
            
        # Recent - check for recent spikes
        recent_spikes = []
        large_trades = []
        new_pins = []
        
        for alert in alerts:
            # Handle both dict and Change object
            if hasattr(alert, 'change_type'):
                alert_type = alert.change_type
                alert_timestamp = alert.timestamp
                alert_details = alert.details
            else:
                alert_type = alert.get('type')
                alert_timestamp = alert.get('timestamp')
                alert_details = alert.get('details', {})
                
            if alert_type == 'SPIKE' and self._is_recent(alert_timestamp):
                recent_spikes.append(alert)
                
            if alert_type == 'SPIKE' and alert_details.get('volume', 0) > 100:
                large_trades.append(alert)
                
            if alert_type == 'NEW_PIN':
                new_pins.append(alert)
        
        scores['recent'] = min(len(recent_spikes) / 3, 1.0)
        scores['institutional'] = min(len(large_trades) / 2, 1.0)
        
        # Persistent - check if pin has been building
        if new_pins:
            scores['persistent'] = 0.9
        else:
            scores['persistent'] = 0.5
            
        # Calculate weighted score
        quality = sum(quality_factors[k] * scores.get(k, 0) for k in quality_factors)
        
        return quality
        
    def _detect_patterns(self, data: Dict) -> List[str]:
        """Detect market patterns affecting confidence"""
        detected = []
        
        for pattern_name, detector in self.patterns.items():
            if detector(data):
                detected.append(pattern_name)
                
        return detected
        
    def _detect_pin_sandwich(self, data: Dict) -> bool:
        """Strong pin with weaker pins on either side"""
        all_pins = sorted(data.get('all_pins', []), key=lambda x: x['strike'])
        
        if len(all_pins) < 3:
            return False
            
        # Find the strongest pin
        strongest_idx = max(range(len(all_pins)), 
                           key=lambda i: all_pins[i].get('force', 0))
        
        # Check if it has neighbors
        if 0 < strongest_idx < len(all_pins) - 1:
            center_force = all_pins[strongest_idx].get('force', 0)
            left_force = all_pins[strongest_idx - 1].get('force', 0)
            right_force = all_pins[strongest_idx + 1].get('force', 0)
            
            # Sandwich if center is much stronger
            return center_force > (left_force + right_force) * 1.5
            
        return False
        
    def _detect_gamma_flip(self, data: Dict) -> bool:
        """Check if near gamma flip level"""
        net_force = data.get('net_force', 0)
        total_gamma = abs(data.get('upward_force', 0)) + abs(data.get('downward_force', 0))
        
        if total_gamma == 0:
            return False
            
        # Near flip if net force is small relative to total
        return abs(net_force) / total_gamma < 0.1
        
    def _detect_competing_pins(self, data: Dict) -> bool:
        """Multiple strong pins fighting for control"""
        top_pins = sorted(data.get('all_pins', []), 
                         key=lambda x: x.get('force', 0), 
                         reverse=True)[:3]
        
        if len(top_pins) < 2:
            return False
            
        # Competing if top 2 are close in strength and opposite directions
        if top_pins[0].get('force', 0) > 0 and top_pins[1].get('force', 0) > 0:
            ratio = top_pins[1]['force'] / top_pins[0]['force']
            return ratio > 0.7  # Within 30% of each other
            
        return False
        
    def _detect_momentum_divergence(self, data: Dict) -> bool:
        """Price moving opposite to gamma force"""
        # This would need price history - simplified version
        alerts = data.get('active_alerts', [])
        
        # Look for direction flips
        flips = []
        for alert in alerts:
            if hasattr(alert, 'change_type'):
                if alert.change_type == 'DIRECTION_FLIP':
                    flips.append(alert)
            else:
                if alert.get('type') == 'DIRECTION_FLIP':
                    flips.append(alert)
        
        return len(flips) > 0
        
    def _detect_volume_surge(self, data: Dict) -> bool:
        """Unusual volume activity"""
        alerts = data.get('active_alerts', [])
        
        # Multiple recent spikes indicate surge
        recent_spikes = []
        for alert in alerts:
            if hasattr(alert, 'change_type'):
                if alert.change_type == 'SPIKE' and self._is_recent(alert.timestamp):
                    recent_spikes.append(alert)
            else:
                if alert.get('type') == 'SPIKE' and self._is_recent(alert.get('timestamp')):
                    recent_spikes.append(alert)
        
        return len(recent_spikes) >= 3
        
    def _is_recent(self, timestamp, minutes: int = 5) -> bool:
        """Check if timestamp is recent"""
        if not timestamp:
            return False
            
        try:
            # Handle both datetime object and string
            if isinstance(timestamp, datetime):
                ts = timestamp
            else:
                ts = datetime.fromisoformat(timestamp)
                
            return (datetime.now() - ts) < timedelta(minutes=minutes)
        except:
            return False
            
    def _adjust_for_patterns(self, confidence: float, patterns: List[str]) -> float:
        """Adjust confidence based on detected patterns"""
        
        adjustments = {
            'pin_sandwich': 1.2,      # Boost - clear target
            'near_gamma_flip': 0.8,   # Reduce - uncertainty
            'competing_pins': 0.7,    # Reduce - conflicting forces
            'momentum_divergence': 0.6,  # Reduce - not aligned
            'volume_surge': 1.1       # Slight boost - activity
        }
        
        for pattern in patterns:
            if pattern in adjustments:
                confidence *= adjustments[pattern]
                
        return min(confidence, 1.0)
        
    def _apply_quality_score(self, confidence: float, data: Dict) -> float:
        """Adjust confidence based on gamma quality"""
        quality = self._calculate_gamma_quality(data)
        
        # Blend confidence with quality (70% confidence, 30% quality)
        return (confidence * 0.7) + (quality * 0.3)
        
    def _apply_dynamic_threshold(self, confidence: float, conditions: MarketConditions) -> float:
        """Apply market condition adjustments"""
        # Already factored into force threshold, so minimal adjustment here
        return confidence
        
    def _calibrate_from_history(self, confidence: float, data: Dict) -> float:
        """Adjust based on historical performance"""
        # Find similar historical setups
        similar_predictions = self._find_similar_predictions(confidence, data)
        
        if len(similar_predictions) >= 10:
            # Calculate actual success rate
            successes = sum(1 for p in similar_predictions if p['outcome'] == 'correct')
            success_rate = successes / len(similar_predictions)
            
            # Blend toward actual success rate
            return (confidence * 0.8) + (success_rate * 0.2)
            
        return confidence
        
    def _find_similar_predictions(self, confidence: float, data: Dict) -> List[Dict]:
        """Find historically similar setups"""
        similar = []
        
        for pred in self.prediction_history:
            # Similar confidence level
            if abs(pred['confidence'] - confidence) < 0.1:
                # Similar market conditions
                if pred.get('direction') == data.get('direction'):
                    similar.append(pred)
                    
        return similar
        
    def _combine_components(self, components: ConfidenceComponents) -> float:
        """Weighted combination of components"""
        return (
            self.weights['force'] * components.force_score +
            self.weights['imbalance'] * components.imbalance_score +
            self.weights['concentration'] * components.concentration_score +
            self.weights['distance'] * components.distance_score +
            self.weights['momentum'] * components.momentum_score
        )
        
    def _generate_explanation(self, components: ConfidenceComponents, 
                            patterns: List[str], final: float) -> List[str]:
        """Generate human-readable explanation"""
        explanation = []
        
        # Component explanations
        if components.force_score > 0.7:
            explanation.append("Strong directional gamma force")
        elif components.force_score < 0.3:
            explanation.append("Weak gamma positioning")
            
        if components.imbalance_score > 0.8:
            explanation.append("Heavily one-sided gamma")
        elif components.imbalance_score < 0.2:
            explanation.append("Balanced gamma (low conviction)")
            
        if components.concentration_score > 0.7:
            explanation.append("Gamma concentrated at key strikes")
            
        if components.distance_score > 0.8:
            explanation.append("Pin very close to current price")
        elif components.distance_score < 0.3:
            explanation.append("Pin far from price (may not act)")
            
        # Pattern explanations
        pattern_explanations = {
            'pin_sandwich': "Clear pin formation with weak neighbors",
            'near_gamma_flip': "Near gamma neutral (uncertain direction)",
            'competing_pins': "Multiple pins competing",
            'momentum_divergence': "Momentum not aligned with gamma",
            'volume_surge': "High volume activity detected"
        }
        
        for pattern in patterns:
            if pattern in pattern_explanations:
                explanation.append(pattern_explanations[pattern])
                
        # Overall assessment
        if final > 0.8:
            explanation.append("HIGH CONFIDENCE setup")
        elif final > 0.6:
            explanation.append("Moderate confidence")
        elif final > 0.4:
            explanation.append("Low confidence - use caution")
        else:
            explanation.append("Very low confidence - avoid trading")
            
        return explanation
        
    def _get_current_conditions(self) -> MarketConditions:
        """Get current market conditions"""
        now = datetime.now()
        return MarketConditions(
            time=now.strftime('%H:%M'),
            vix=15.0,  # Would get from market data
            volume_percentile=50.0,  # Would calculate from historical
            days_to_expiry=0  # 0DTE
        )
        
    def record_outcome(self, prediction_data: Dict, outcome: str):
        """Record prediction outcome for future calibration"""
        self.prediction_history.append({
            'timestamp': datetime.now(),
            'confidence': prediction_data['confidence'],
            'direction': prediction_data['direction'],
            'patterns': prediction_data.get('patterns', []),
            'outcome': outcome  # 'correct', 'incorrect', 'neutral'
        })