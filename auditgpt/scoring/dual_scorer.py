"""
Dual scoring system for AuditGPT.

Produces separate scores for:
1. Manipulation/fraud-risk
2. Financial-stress/asset-quality
3. Combined forensic attention score

Uses Forensic Sigmoid methodology to avoid extreme 0/100 scores.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any, Literal
import numpy as np

from auditgpt.signals.base import Signal, SignalSeverity, SignalCategory
from auditgpt.config.constants import SEVERITY_WEIGHTS, RECENCY_WEIGHTS, RECENCY_WEIGHTS_CRITICAL


@dataclass
class DualScore:
    """
    Dual score output with separate manipulation and stress scores.
    
    For banks:
    - Make asset-quality/provisioning/capital/liquidity issues primary in stress score
    - Do not overlabel ordinary banking stress as manipulation unless corroborating evidence
    """
    
    # Manipulation/fraud-risk score (required fields first)
    manipulation_score: float
    manipulation_level: Literal['CRITICAL', 'HIGH', 'MEDIUM', 'LOW']
    
    # Financial-stress score (required fields)
    stress_score: float
    stress_level: Literal['CRITICAL', 'HIGH', 'MEDIUM', 'LOW']
    
    # Fields with defaults
    manipulation_signal_count: int = 0
    manipulation_critical_count: int = 0
    stress_signal_count: int = 0
    stress_critical_count: int = 0
    
    # Combined score
    combined_score: float = 0
    combined_level: Literal['CRITICAL', 'HIGH', 'MEDIUM', 'LOW'] = 'LOW'
    
    # Score breakdown for transparency
    score_breakdown: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Calculate combined score if not set."""
        if self.combined_score == 0:
            # Weighted combination: manipulation signals are weighted higher for fraud risk
            self.combined_score = 0.6 * self.manipulation_score + 0.4 * self.stress_score
        
        if self.combined_level == 'LOW':
            self.combined_level = self._get_level(self.combined_score)
    
    def _get_level(self, score: float) -> Literal['CRITICAL', 'HIGH', 'MEDIUM', 'LOW']:
        """Determine risk level from score."""
        if score >= 70:
            return 'CRITICAL'
        elif score >= 45:
            return 'HIGH'
        elif score >= 25:
            return 'MEDIUM'
        else:
            return 'LOW'
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'manipulation_score': round(self.manipulation_score, 1),
            'manipulation_level': self.manipulation_level,
            'manipulation_signal_count': self.manipulation_signal_count,
            'manipulation_critical_count': self.manipulation_critical_count,
            'stress_score': round(self.stress_score, 1),
            'stress_level': self.stress_level,
            'stress_signal_count': self.stress_signal_count,
            'stress_critical_count': self.stress_critical_count,
            'combined_score': round(self.combined_score, 1),
            'combined_level': self.combined_level,
            'score_breakdown': self.score_breakdown,
        }


class DualScorer:
    """
    Advanced dual scoring using Forensic Sigmoid methodology.
    
    Key principles:
    1. Base risk of 8-10 (no company is perfect)
    2. Diminishing returns for multiple anomalies of same type
    3. Recency weighting (recent issues score higher)
    4. Sigmoid curve to avoid 0/100 extremes
    5. Separate manipulation vs stress scoring
    6. Peer comparison adjustment
    """
    
    # Base risk - no company is perfect
    BASE_RISK = 8
    
    # Maximum achievable score
    MAX_SCORE = 95
    
    def __init__(
        self,
        base_risk: float = 8,
        max_score: float = 95,
        manipulation_weight: float = 0.6,
        stress_weight: float = 0.4,
    ):
        """
        Initialize the dual scorer.
        
        Args:
            base_risk: Minimum score (accounts for unknown unknowns)
            max_score: Maximum score cap
            manipulation_weight: Weight for manipulation score in combined
            stress_weight: Weight for stress score in combined
        """
        self.base_risk = base_risk
        self.max_score = max_score
        self.manipulation_weight = manipulation_weight
        self.stress_weight = stress_weight
    
    def score(
        self,
        signals: List[Signal],
        peer_comparison: Optional[Dict[str, Any]] = None,
        current_year: int = 2025,
        sector: str = 'DEFAULT',
    ) -> DualScore:
        """
        Calculate dual scores for manipulation and stress.
        
        Args:
            signals: List of detected signals
            peer_comparison: Peer benchmark data
            current_year: Current year for recency calculation
            sector: Company sector code
            
        Returns:
            DualScore with separate manipulation and stress scores
        """
        # Separate signals by category
        manipulation_signals = [
            s for s in signals
            if s.manipulation_or_stress in (SignalCategory.MANIPULATION, SignalCategory.BOTH)
            and s.current_severity != SignalSeverity.INFO
        ]
        
        stress_signals = [
            s for s in signals
            if s.manipulation_or_stress in (SignalCategory.STRESS, SignalCategory.BOTH)
            and s.current_severity != SignalSeverity.INFO
        ]
        
        # Calculate individual scores
        manipulation_raw, manipulation_breakdown = self._compute_raw_score(
            manipulation_signals, current_year
        )
        stress_raw, stress_breakdown = self._compute_raw_score(
            stress_signals, current_year
        )
        
        # Apply sigmoid transformation
        manipulation_score = self._sigmoid_transform(manipulation_raw)
        stress_score = self._sigmoid_transform(stress_raw)
        
        # Apply peer comparison adjustment
        if peer_comparison:
            manipulation_score = self._apply_peer_adjustment(manipulation_score, peer_comparison)
            stress_score = self._apply_peer_adjustment(stress_score, peer_comparison)
        
        # Count critical signals
        manip_critical = sum(
            1 for s in manipulation_signals if s.current_severity == SignalSeverity.CRITICAL
        )
        stress_critical = sum(
            1 for s in stress_signals if s.current_severity == SignalSeverity.CRITICAL
        )
        
        # Determine levels
        manipulation_level = self._get_level(manipulation_score, manip_critical, len(manipulation_signals))
        stress_level = self._get_level(stress_score, stress_critical, len(stress_signals))
        
        # Calculate combined score
        combined_score = (
            self.manipulation_weight * manipulation_score +
            self.stress_weight * stress_score
        )
        
        # Ensure bounds
        manipulation_score = max(self.base_risk, min(self.max_score, manipulation_score))
        stress_score = max(self.base_risk, min(self.max_score, stress_score))
        combined_score = max(self.base_risk, min(self.max_score, combined_score))
        
        return DualScore(
            manipulation_score=round(manipulation_score, 1),
            manipulation_level=manipulation_level,
            manipulation_signal_count=len(manipulation_signals),
            manipulation_critical_count=manip_critical,
            stress_score=round(stress_score, 1),
            stress_level=stress_level,
            stress_signal_count=len(stress_signals),
            stress_critical_count=stress_critical,
            combined_score=round(combined_score, 1),
            combined_level=self._get_level(
                combined_score,
                manip_critical + stress_critical,
                len(manipulation_signals) + len(stress_signals)
            ),
            score_breakdown={
                'manipulation': manipulation_breakdown,
                'stress': stress_breakdown,
                'peer_adjusted': peer_comparison is not None,
            },
        )
    
    def _compute_raw_score(
        self,
        signals: List[Signal],
        current_year: int
    ) -> tuple[float, Dict[str, Any]]:
        """
        Compute raw score from signals with diminishing returns and recency.
        
        Returns:
            Tuple of (raw_score, breakdown_dict)
        """
        if not signals:
            return self.base_risk, {'signal_contributions': [], 'total_raw': self.base_risk}
        
        raw_score = self.base_risk
        contributions = []
        
        # Group by signal family for diminishing returns
        by_family = {}
        for signal in signals:
            family = signal.signal_family.value
            if family not in by_family:
                by_family[family] = []
            by_family[family].append(signal)
        
        for family, family_signals in by_family.items():
            # Sort by severity (most severe first)
            family_signals.sort(
                key=lambda x: ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW'].index(x.current_severity.value)
            )
            
            for i, signal in enumerate(family_signals):
                severity = signal.current_severity.value
                base_weight = SEVERITY_WEIGHTS.get(severity, 2)
                
                # Diminishing returns: 1st=100%, 2nd=60%, 3rd=40%, 4th+=20%
                diminishing_factor = [1.0, 0.6, 0.4, 0.2][min(i, 3)]
                
                # Recency weighting
                try:
                    years_ago = current_year - signal.year_latest
                except:
                    years_ago = 3
                
                years_ago = max(0, min(years_ago, 5))
                
                if severity == 'CRITICAL':
                    recency_factor = RECENCY_WEIGHTS_CRITICAL.get(years_ago, 0.85)
                else:
                    recency_factor = RECENCY_WEIGHTS.get(years_ago, 0.7)
                
                # Calculate contribution
                contribution = base_weight * diminishing_factor * recency_factor
                raw_score += contribution
                
                contributions.append({
                    'signal_id': signal.signal_id,
                    'family': family,
                    'severity': severity,
                    'year': signal.year_latest,
                    'base_weight': base_weight,
                    'diminishing_factor': diminishing_factor,
                    'recency_factor': recency_factor,
                    'contribution': round(contribution, 2),
                })
        
        return raw_score, {
            'signal_contributions': contributions,
            'total_raw': round(raw_score, 2),
        }
    
    def _sigmoid_transform(self, raw_score: float) -> float:
        """
        Apply sigmoid-like transformation to raw score.
        
        Ensures score stays between BASE_RISK and MAX_SCORE.
        Provides diminishing returns as score increases.
        """
        # Normalize: map raw_score to 0-1 range (assume 120 is max raw)
        normalized = min(raw_score / 120, 1.0)
        
        # Apply soft sigmoid (power < 1 creates concave curve)
        sigmoid = normalized ** 0.7
        
        # Map to final range
        score = self.base_risk + (self.max_score - self.base_risk) * sigmoid
        
        return score
    
    def _apply_peer_adjustment(
        self,
        score: float,
        peer_comparison: Dict[str, Any]
    ) -> float:
        """Adjust score based on peer comparison."""
        if not peer_comparison or not peer_comparison.get('comparisons'):
            return score
        
        comparisons = peer_comparison['comparisons']
        if not comparisons:
            return score
        
        above_peer_count = sum(
            1 for c in comparisons if c.get('position') in ['ABOVE', 'BETTER']
        )
        below_peer_count = sum(
            1 for c in comparisons if c.get('position') in ['BELOW', 'WORSE']
        )
        total = len(comparisons)
        
        if total > 0:
            # Calculate net peer position (-1 to +1)
            net_position = (above_peer_count - below_peer_count) / total
            
            # Adjust score by up to 15% based on peer position
            adjustment = net_position * 0.15 * score
            score = score - adjustment  # Better than peers = lower risk
        
        return score
    
    def _get_level(
        self,
        score: float,
        critical_count: int,
        total_count: int
    ) -> Literal['CRITICAL', 'HIGH', 'MEDIUM', 'LOW']:
        """Determine risk level from score and signal counts."""
        # Critical if score high OR multiple critical signals
        if score >= 70 or critical_count >= 2:
            return 'CRITICAL'
        elif score >= 45 or critical_count >= 1 or total_count >= 5:
            return 'HIGH'
        elif score >= 25:
            return 'MEDIUM'
        else:
            return 'LOW'


def calculate_legacy_score(
    signals: List[Signal],
    peer_comparison: Optional[Dict[str, Any]] = None,
    current_year: int = 2025,
) -> tuple[float, str]:
    """
    Calculate a single legacy score for backward compatibility.
    
    Returns:
        Tuple of (score, risk_level)
    """
    scorer = DualScorer()
    dual_score = scorer.score(signals, peer_comparison, current_year)
    
    return dual_score.combined_score, dual_score.combined_level
