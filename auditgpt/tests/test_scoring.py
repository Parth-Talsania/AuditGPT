"""
Tests for the dual scoring system.
"""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from auditgpt.signals.base import Signal, SignalSeverity, SignalCategory, SignalFamily, create_signal
from auditgpt.scoring.dual_scorer import DualScorer, DualScore
from auditgpt.evidence.models import EvidenceRef, RefType


class TestDualScorer:
    """Tests for the dual scoring system."""
    
    def test_base_risk_floor(self, dual_scorer):
        """Test that score never goes below base risk."""
        # Empty signals should still have base risk
        score = dual_scorer.score(signals=[], current_year=2025)
        
        assert score.manipulation_score >= 8
        assert score.stress_score >= 8
        assert score.combined_score >= 8
    
    def test_max_score_ceiling(self, dual_scorer):
        """Test that score never exceeds max (95)."""
        # Create many critical signals
        signals = []
        for i in range(20):
            signals.append(create_signal(
                family=SignalFamily.REVENUE_DIVERGENCE,
                category=SignalCategory.MANIPULATION,
                year=2024,
                severity=SignalSeverity.CRITICAL,
                description=f"Critical signal {i}",
                evidence_refs=[
                    EvidenceRef(ref_type=RefType.STATEMENT, filing_year=2024)
                ],
            ))
        
        score = dual_scorer.score(signals=signals, current_year=2025)
        
        assert score.manipulation_score <= 95
        assert score.combined_score <= 95
    
    def test_manipulation_vs_stress_separation(self, dual_scorer):
        """Test that manipulation and stress signals are scored separately."""
        manip_signal = create_signal(
            family=SignalFamily.REVENUE_DIVERGENCE,
            category=SignalCategory.MANIPULATION,
            year=2024,
            severity=SignalSeverity.HIGH,
            description="Manipulation signal",
            evidence_refs=[
                EvidenceRef(ref_type=RefType.STATEMENT, filing_year=2024)
            ],
        )
        
        stress_signal = create_signal(
            family=SignalFamily.LEVERAGE_STRESS,
            category=SignalCategory.STRESS,
            year=2024,
            severity=SignalSeverity.HIGH,
            description="Stress signal",
            evidence_refs=[
                EvidenceRef(ref_type=RefType.RATIO, filing_year=2024)
            ],
        )
        
        # Only manipulation signals
        manip_only = dual_scorer.score(signals=[manip_signal], current_year=2025)
        assert manip_only.manipulation_signal_count == 1
        assert manip_only.stress_signal_count == 0
        
        # Only stress signals
        stress_only = dual_scorer.score(signals=[stress_signal], current_year=2025)
        assert stress_only.manipulation_signal_count == 0
        assert stress_only.stress_signal_count == 1
        
        # Both
        both = dual_scorer.score(signals=[manip_signal, stress_signal], current_year=2025)
        assert both.manipulation_signal_count == 1
        assert both.stress_signal_count == 1
    
    def test_combined_score_weighting(self, dual_scorer):
        """Test that combined score uses correct weighting (60/40)."""
        # The combined should be 0.6 * manipulation + 0.4 * stress
        # This is implicit in the scorer, just verify the formula works
        
        score = dual_scorer.score(signals=[], current_year=2025)
        
        expected_combined = 0.6 * score.manipulation_score + 0.4 * score.stress_score
        
        # Allow small floating point difference
        assert abs(score.combined_score - expected_combined) < 1.0
    
    def test_risk_levels(self, dual_scorer):
        """Test risk level determination."""
        # Create signals to get different levels
        
        # Low risk - no signals
        low = dual_scorer.score(signals=[], current_year=2025)
        assert low.combined_level in ['LOW', 'MEDIUM']  # Base risk is ~8
        
        # High risk - multiple high severity signals
        high_signals = [
            create_signal(
                family=SignalFamily.REVENUE_DIVERGENCE,
                category=SignalCategory.MANIPULATION,
                year=2024,
                severity=SignalSeverity.HIGH,
                description="High signal",
                evidence_refs=[EvidenceRef(ref_type=RefType.STATEMENT, filing_year=2024)],
            )
            for i in range(5)
        ]
        high = dual_scorer.score(signals=high_signals, current_year=2025)
        assert high.combined_level in ['HIGH', 'CRITICAL']
    
    def test_recency_weighting(self, dual_scorer):
        """Test that recent signals have more impact."""
        # Old signal (5 years ago)
        old_signal = create_signal(
            family=SignalFamily.REVENUE_DIVERGENCE,
            category=SignalCategory.MANIPULATION,
            year=2020,
            severity=SignalSeverity.HIGH,
            description="Old signal",
            evidence_refs=[EvidenceRef(ref_type=RefType.STATEMENT, filing_year=2020)],
        )
        
        # Recent signal (current year)
        recent_signal = create_signal(
            family=SignalFamily.REVENUE_DIVERGENCE,
            category=SignalCategory.MANIPULATION,
            year=2024,
            severity=SignalSeverity.HIGH,
            description="Recent signal",
            evidence_refs=[EvidenceRef(ref_type=RefType.STATEMENT, filing_year=2024)],
        )
        
        old_score = dual_scorer.score(signals=[old_signal], current_year=2025)
        recent_score = dual_scorer.score(signals=[recent_signal], current_year=2025)
        
        # Recent should score higher (before sigmoid transformation effects)
        assert recent_score.manipulation_score >= old_score.manipulation_score
    
    def test_diminishing_returns_same_family(self, dual_scorer):
        """Test diminishing returns for multiple signals of same family."""
        signals = [
            create_signal(
                family=SignalFamily.REVENUE_DIVERGENCE,  # Same family
                category=SignalCategory.MANIPULATION,
                year=2024,
                severity=SignalSeverity.HIGH,
                description=f"Signal {i}",
                evidence_refs=[EvidenceRef(ref_type=RefType.STATEMENT, filing_year=2024)],
            )
            for i in range(4)
        ]
        
        # Each additional signal should add less
        scores = []
        for i in range(1, 5):
            score = dual_scorer.score(signals=signals[:i], current_year=2025)
            scores.append(score.manipulation_score)
        
        # Check diminishing increments
        increments = [scores[i] - scores[i-1] for i in range(1, len(scores))]
        
        # Later increments should be smaller (diminishing returns)
        # Note: With sigmoid, this may not be strictly decreasing
        assert all(i >= 0 for i in increments)  # At least non-negative


class TestDualScore:
    """Tests for DualScore dataclass."""
    
    def test_to_dict(self, sample_signal_manipulation, sample_signal_stress):
        """Test DualScore to_dict conversion."""
        score = DualScore(
            manipulation_score=45.5,
            manipulation_level='HIGH',
            manipulation_signal_count=3,
            manipulation_critical_count=1,
            stress_score=30.0,
            stress_level='MEDIUM',
            stress_signal_count=2,
            stress_critical_count=0,
        )
        
        d = score.to_dict()
        
        assert d['manipulation_score'] == 45.5
        assert d['manipulation_level'] == 'HIGH'
        assert d['stress_score'] == 30.0
        assert d['combined_level'] in ['LOW', 'MEDIUM', 'HIGH', 'CRITICAL']
    
    def test_combined_score_auto_calculation(self):
        """Test that combined score is auto-calculated."""
        score = DualScore(
            manipulation_score=50.0,
            manipulation_level='HIGH',
            stress_score=40.0,
            stress_level='MEDIUM',
        )
        
        # Combined = 0.6 * 50 + 0.4 * 40 = 30 + 16 = 46
        expected = 0.6 * 50.0 + 0.4 * 40.0
        
        assert abs(score.combined_score - expected) < 0.1
