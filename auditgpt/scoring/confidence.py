"""
Confidence calibration for AuditGPT signals.

Adjusts signal confidence based on:
- Evidence quality and quantity
- Historical accuracy of similar signals
- Data completeness
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from auditgpt.signals.base import Signal, SignalSeverity
from auditgpt.evidence.models import EvidenceRef, RefType


@dataclass
class ConfidenceFactors:
    """Factors that affect confidence calculation."""
    
    evidence_quality: float = 1.0  # 0.5 - 1.5
    data_completeness: float = 1.0  # 0.5 - 1.2
    historical_accuracy: float = 1.0  # 0.8 - 1.2
    peer_corroboration: float = 1.0  # 0.9 - 1.1
    
    @property
    def combined_factor(self) -> float:
        """Calculate combined confidence adjustment factor."""
        return (
            self.evidence_quality * 0.4 +
            self.data_completeness * 0.3 +
            self.historical_accuracy * 0.2 +
            self.peer_corroboration * 0.1
        )


class ConfidenceCalibrator:
    """
    Calibrates confidence levels for signals.
    
    Principle: If something is uncertain, lower confidence instead of
    inventing certainty.
    """
    
    # Base confidence by signal type
    BASE_CONFIDENCE = {
        'revenue_divergence': 0.85,
        'profit_quality': 0.80,
        'receivables_spike': 0.75,
        'rpt_anomaly': 0.60,  # Lower - often based on proxy
        'auditor_escalation': 0.70,  # Depends on note availability
        'one_time_gain': 0.60,  # Proxy-based
        'leverage_stress': 0.85,
        'asset_quality': 0.90,
        'capital_adequacy': 0.95,  # Regulatory data
        'profitability_collapse': 0.90,
        'weak_cfo': 0.85,
        'roce_decline': 0.80,
    }
    
    def calibrate_signal(
        self,
        signal: Signal,
        data_availability: Dict[str, bool],
        has_real_notes: bool = False,
    ) -> float:
        """
        Calibrate confidence for a single signal.
        
        Args:
            signal: The signal to calibrate
            data_availability: Dict of what data is available
            has_real_notes: Whether real annual report notes were parsed
            
        Returns:
            Calibrated confidence value (0.0 - 1.0)
        """
        # Start with base confidence for signal family
        base = self.BASE_CONFIDENCE.get(signal.signal_family.value, 0.75)
        
        factors = ConfidenceFactors()
        
        # Evidence quality factor
        factors.evidence_quality = self._assess_evidence_quality(signal.evidence_refs)
        
        # Data completeness factor
        factors.data_completeness = self._assess_data_completeness(
            signal, data_availability
        )
        
        # Real notes availability boost
        if signal.signal_family.value in ['auditor_escalation', 'rpt_anomaly']:
            if has_real_notes:
                factors.evidence_quality *= 1.2
            else:
                factors.evidence_quality *= 0.7  # Lower if using proxy/mock
        
        # Calculate final confidence
        confidence = base * factors.combined_factor
        
        # Clamp to valid range
        return max(0.1, min(1.0, confidence))
    
    def calibrate_all_signals(
        self,
        signals: List[Signal],
        data_availability: Dict[str, bool],
        has_real_notes: bool = False,
    ) -> List[Signal]:
        """
        Calibrate confidence for all signals.
        
        Args:
            signals: List of signals to calibrate
            data_availability: Dict of what data is available
            has_real_notes: Whether real notes were parsed
            
        Returns:
            List of signals with calibrated confidence
        """
        for signal in signals:
            signal.confidence = self.calibrate_signal(
                signal, data_availability, has_real_notes
            )
        
        return signals
    
    def _assess_evidence_quality(self, evidence_refs: List[EvidenceRef]) -> float:
        """Assess the quality of evidence references."""
        if not evidence_refs:
            return 0.5  # No evidence = low quality
        
        quality_score = 0.7  # Start at base
        
        for ref in evidence_refs:
            # Statement refs are high quality (concrete numbers)
            if ref.ref_type == RefType.STATEMENT:
                quality_score += 0.1
            
            # Note refs with page numbers are better
            elif ref.ref_type == RefType.NOTE:
                if ref.page_number:
                    quality_score += 0.1
                if ref.snippet:
                    quality_score += 0.05
        
        return min(1.3, quality_score)  # Cap at 1.3
    
    def _assess_data_completeness(
        self,
        signal: Signal,
        data_availability: Dict[str, bool]
    ) -> float:
        """Assess data completeness for signal type."""
        completeness = 1.0
        
        family = signal.signal_family.value
        
        # CFO-related signals need cash flow data
        if family in ['revenue_divergence', 'profit_quality', 'weak_cfo']:
            if not data_availability.get('cash_flow', True):
                completeness *= 0.6
        
        # Balance sheet signals
        if family in ['leverage_stress', 'receivables_spike']:
            if not data_availability.get('balance_sheet', True):
                completeness *= 0.6
        
        # Bank-specific signals need ratios
        if family in ['asset_quality', 'capital_adequacy']:
            if not data_availability.get('ratios', True):
                completeness *= 0.7
        
        # Auditor signals need notes
        if family == 'auditor_escalation':
            if not data_availability.get('auditor_notes', False):
                completeness *= 0.5
        
        return completeness
    
    def get_uncertainty_disclosure(
        self,
        signals: List[Signal],
        data_availability: Dict[str, bool],
        has_real_notes: bool = False,
    ) -> List[str]:
        """
        Generate uncertainty disclosures for the report.
        
        Returns list of disclosure statements about analysis limitations.
        """
        disclosures = []
        
        # Check for missing data
        if not data_availability.get('cash_flow', True):
            disclosures.append(
                "Cash flow statement data unavailable - CFO-based signals may be incomplete."
            )
        
        if not data_availability.get('ratios', True):
            disclosures.append(
                "Ratio data unavailable - some metric comparisons not performed."
            )
        
        # Note availability
        if not has_real_notes:
            if any(s.signal_family.value == 'auditor_escalation' for s in signals):
                disclosures.append(
                    "Auditor sentiment analysis based on simulated data - "
                    "actual annual report parsing not performed."
                )
            
            if any(s.signal_family.value == 'rpt_anomaly' for s in signals):
                disclosures.append(
                    "Related party transaction analysis uses proxy indicators (Other Income) - "
                    "actual RPT note parsing not performed."
                )
        
        # Low confidence signals
        low_confidence_signals = [s for s in signals if s.confidence < 0.6]
        if low_confidence_signals:
            families = set(s.signal_family.value for s in low_confidence_signals)
            disclosures.append(
                f"Some signals have reduced confidence due to data limitations: "
                f"{', '.join(families)}"
            )
        
        return disclosures
