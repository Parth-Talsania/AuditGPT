"""
Base signal classes for AuditGPT anomaly detection.

Every signal must include:
- signal_id: Unique identifier
- signal_family: Category of anomaly
- manipulation_or_stress: Classification for dual scoring
- year_first_seen: When anomaly started
- current_severity: CRITICAL/HIGH/MEDIUM/LOW
- evidence_refs: List of source references
- confidence: 0.0 to 1.0
"""

from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Literal
from enum import Enum
import uuid

from auditgpt.evidence.models import EvidenceRef


class SignalSeverity(str, Enum):
    """Severity level of a signal."""
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"  # Informational only, not a risk


class SignalCategory(str, Enum):
    """Whether signal indicates manipulation or stress."""
    MANIPULATION = "manipulation"
    STRESS = "stress"
    BOTH = "both"


class SignalFamily(str, Enum):
    """Family/category of signals."""
    # Manipulation signals
    REVENUE_DIVERGENCE = "revenue_divergence"
    PROFIT_QUALITY = "profit_quality"
    RECEIVABLES_SPIKE = "receivables_spike"
    RPT_ANOMALY = "rpt_anomaly"
    AUDITOR_ESCALATION = "auditor_escalation"
    DISCLOSURE_ANOMALY = "disclosure_anomaly"
    ONE_TIME_GAIN = "one_time_gain"
    
    # Stress signals
    LEVERAGE_STRESS = "leverage_stress"
    INTEREST_COVERAGE = "interest_coverage"
    LIQUIDITY_PRESSURE = "liquidity_pressure"
    CAPITAL_ADEQUACY = "capital_adequacy"
    ASSET_QUALITY = "asset_quality"
    PROVISIONING = "provisioning"
    PROFITABILITY_COLLAPSE = "profitability_collapse"
    WEAK_CFO = "weak_cfo"
    ROCE_DECLINE = "roce_decline"
    
    # Informational
    STRUCTURAL_BREAK = "structural_break"


@dataclass
class Signal:
    """
    Base class for all forensic signals.
    
    Every signal must carry evidence references from source documents.
    Do not claim exact filing line reference unless page/note/paragraph
    references actually exist in the evidence store.
    """
    
    signal_id: str
    signal_family: SignalFamily
    manipulation_or_stress: SignalCategory
    
    # Timing
    year_first_seen: int
    year_latest: int
    
    # Severity and confidence
    current_severity: SignalSeverity
    confidence: float  # 0.0 to 1.0
    
    # Evidence (REQUIRED - every signal must have evidence)
    evidence_refs: List[EvidenceRef] = field(default_factory=list)
    
    # Descriptions
    description: str = ""
    pattern: str = ""  # What fraud pattern this matches
    explanation_seed: str = ""  # Template for report generation
    
    # Comparisons
    company_history_comparison: Optional[str] = None  # "3σ above historical mean"
    peer_comparison: Optional[str] = None  # "Worst in peer group"
    
    # Legacy compatibility
    anomaly_type: Optional[str] = None  # Maps to old 'type' field
    
    def __post_init__(self):
        """Validate signal has required data."""
        if not self.signal_id:
            self.signal_id = str(uuid.uuid4())[:8]
        
        if self.confidence < 0:
            self.confidence = 0.0
        elif self.confidence > 1:
            self.confidence = 1.0
    
    @property
    def is_manipulation_signal(self) -> bool:
        """Check if this signal indicates manipulation risk."""
        return self.manipulation_or_stress in (SignalCategory.MANIPULATION, SignalCategory.BOTH)
    
    @property
    def is_stress_signal(self) -> bool:
        """Check if this signal indicates financial stress."""
        return self.manipulation_or_stress in (SignalCategory.STRESS, SignalCategory.BOTH)
    
    @property
    def has_evidence(self) -> bool:
        """Check if signal has any evidence references."""
        return len(self.evidence_refs) > 0
    
    @property
    def primary_citation(self) -> str:
        """Get the primary citation string for this signal."""
        if self.evidence_refs:
            return self.evidence_refs[0].citation_string
        return f"FY{self.year_latest}"
    
    @property
    def all_citations(self) -> List[str]:
        """Get all citation strings for this signal."""
        return [ref.citation_string for ref in self.evidence_refs]
    
    def to_legacy_dict(self) -> Dict[str, Any]:
        """
        Convert to legacy anomaly dict format for backward compatibility.
        
        Returns dict matching old AnomalyDetector output format.
        """
        return {
            'type': self.anomaly_type or self.signal_family.value,
            'year': self.year_latest,
            'severity': self.current_severity.value,
            'description': self.description,
            'pattern': self.pattern,
            'statement_type': self._get_statement_type(),
            'source_reference': self.primary_citation,
            # New fields
            'signal_id': self.signal_id,
            'manipulation_or_stress': self.manipulation_or_stress.value,
            'confidence': self.confidence,
            'evidence_refs': [ref.to_dict() for ref in self.evidence_refs],
        }
    
    def _get_statement_type(self) -> str:
        """Extract statement type from evidence refs."""
        for ref in self.evidence_refs:
            if ref.statement_type:
                return ref.statement_type
        
        # Fallback based on signal family
        family_to_statement = {
            SignalFamily.REVENUE_DIVERGENCE: 'P&L + Cash Flow Statement',
            SignalFamily.PROFIT_QUALITY: 'P&L + Cash Flow Statement',
            SignalFamily.RECEIVABLES_SPIKE: 'Balance Sheet',
            SignalFamily.LEVERAGE_STRESS: 'Balance Sheet',
            SignalFamily.ASSET_QUALITY: 'Financial Ratios',
            SignalFamily.AUDITOR_ESCALATION: 'Auditor Report',
        }
        return family_to_statement.get(self.signal_family, 'Financial Data')
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to full dictionary representation."""
        return {
            'signal_id': self.signal_id,
            'signal_family': self.signal_family.value,
            'manipulation_or_stress': self.manipulation_or_stress.value,
            'year_first_seen': self.year_first_seen,
            'year_latest': self.year_latest,
            'current_severity': self.current_severity.value,
            'confidence': self.confidence,
            'description': self.description,
            'pattern': self.pattern,
            'explanation_seed': self.explanation_seed,
            'company_history_comparison': self.company_history_comparison,
            'peer_comparison': self.peer_comparison,
            'evidence_refs': [ref.to_dict() for ref in self.evidence_refs],
            'has_evidence': self.has_evidence,
            'primary_citation': self.primary_citation,
        }


def create_signal(
    family: SignalFamily,
    category: SignalCategory,
    year: int,
    severity: SignalSeverity,
    description: str,
    evidence_refs: List[EvidenceRef],
    pattern: str = "",
    confidence: float = 0.8,
    anomaly_type: Optional[str] = None,
    company_comparison: Optional[str] = None,
    peer_comparison: Optional[str] = None,
) -> Signal:
    """
    Factory function to create a Signal with proper defaults.
    
    Args:
        family: Signal family classification
        category: manipulation/stress/both
        year: Year the signal was detected
        severity: Severity level
        description: Human-readable description
        evidence_refs: List of evidence references (required)
        pattern: Fraud pattern this matches
        confidence: Confidence level 0-1
        anomaly_type: Legacy type name for backward compatibility
        company_comparison: How this compares to company history
        peer_comparison: How this compares to peers
        
    Returns:
        Configured Signal instance
    """
    return Signal(
        signal_id=str(uuid.uuid4())[:8],
        signal_family=family,
        manipulation_or_stress=category,
        year_first_seen=year,
        year_latest=year,
        current_severity=severity,
        confidence=confidence,
        evidence_refs=evidence_refs,
        description=description,
        pattern=pattern,
        anomaly_type=anomaly_type,
        company_history_comparison=company_comparison,
        peer_comparison=peer_comparison,
    )
