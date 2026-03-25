"""
Evidence models for AuditGPT.

Defines data structures for evidence references, note chunks, and citations.
Every signal must carry evidence references from source documents.
"""

from dataclasses import dataclass, field
from typing import Optional, List, Literal, Dict, Any
from enum import Enum


class RefType(str, Enum):
    """Type of evidence reference."""
    STATEMENT = "statement"
    NOTE = "note"
    RATIO = "ratio"


class SectionType(str, Enum):
    """Type of annual report section."""
    AUDITOR_NOTE = "auditor_note"
    RELATED_PARTY = "related_party"
    MDA = "mda"  # Management Discussion & Analysis
    RISK = "risk"
    OTHER = "other"


@dataclass
class EvidenceRef:
    """
    Reference to evidence supporting a signal or finding.
    
    Every anomaly must point to specific evidence with:
    - Filing year
    - Statement type or note type
    - Page number (for notes)
    - Note number or heading
    - Paragraph index
    - Snippet text
    """
    
    ref_type: RefType
    filing_year: int
    
    # For statement refs (P&L, Balance Sheet, Cash Flow)
    statement_type: Optional[str] = None
    line_item: Optional[str] = None
    
    # For note refs (annual report sections)
    note_type: Optional[SectionType] = None
    page_number: Optional[int] = None
    note_number: Optional[str] = None
    note_heading: Optional[str] = None
    paragraph_index: Optional[int] = None
    
    # Actual text snippet (max 200 chars)
    snippet: Optional[str] = None
    
    # Source file path (for traceability)
    source_file: Optional[str] = None
    
    @property
    def citation_string(self) -> str:
        """Generate a human-readable citation string."""
        if self.ref_type == RefType.STATEMENT:
            parts = []
            if self.statement_type:
                parts.append(self.statement_type)
            if self.line_item:
                parts.append(self.line_item)
            parts.append(f"FY{self.filing_year}")
            return " > ".join(parts)
            
        elif self.ref_type == RefType.NOTE:
            parts = [f"Annual Report FY{self.filing_year}"]
            if self.page_number:
                parts.append(f"Page {self.page_number}")
            if self.note_number:
                parts.append(f"Note {self.note_number}")
            elif self.note_heading:
                parts.append(f"Section: {self.note_heading[:50]}")
            return " > ".join(parts)
            
        elif self.ref_type == RefType.RATIO:
            return f"Financial Ratios > FY{self.filing_year}"
        
        return f"FY{self.filing_year}"
    
    @property
    def short_citation(self) -> str:
        """Generate a short citation for inline use."""
        if self.ref_type == RefType.STATEMENT:
            return f"{self.statement_type} FY{self.filing_year}"
        elif self.ref_type == RefType.NOTE:
            if self.page_number:
                return f"AR FY{self.filing_year} p.{self.page_number}"
            return f"AR FY{self.filing_year}"
        return f"FY{self.filing_year}"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'ref_type': self.ref_type.value if isinstance(self.ref_type, RefType) else self.ref_type,
            'filing_year': self.filing_year,
            'statement_type': self.statement_type,
            'line_item': self.line_item,
            'note_type': self.note_type.value if isinstance(self.note_type, SectionType) else self.note_type,
            'page_number': self.page_number,
            'note_number': self.note_number,
            'note_heading': self.note_heading,
            'paragraph_index': self.paragraph_index,
            'snippet': self.snippet,
            'source_file': self.source_file,
            'citation': self.citation_string,
        }


@dataclass
class StatementRef:
    """
    Reference to a specific line in a financial statement.
    
    Used for statement-table-based anomalies.
    """
    statement_type: str  # 'P&L', 'Balance Sheet', 'Cash Flow', 'Ratios'
    line_item: str
    filing_year: int
    value: Optional[float] = None
    
    def to_evidence_ref(self) -> EvidenceRef:
        """Convert to EvidenceRef for uniform handling."""
        return EvidenceRef(
            ref_type=RefType.STATEMENT,
            filing_year=self.filing_year,
            statement_type=self.statement_type,
            line_item=self.line_item,
        )


@dataclass
class NoteChunk:
    """
    A chunk of text extracted from an annual report.
    
    Used for storing parsed sections from PDFs:
    - Auditor reports
    - Related party disclosures
    - Management discussion sections
    """
    company: str
    filing_year: int
    source_file: str
    page_number: int
    text: str
    section_type: SectionType
    
    # Optional metadata
    note_heading: Optional[str] = None
    note_number: Optional[str] = None
    paragraph_index: int = 0
    
    # For retrieval
    embedding: Optional[List[float]] = None
    
    def to_evidence_ref(self) -> EvidenceRef:
        """Convert to EvidenceRef for citation."""
        return EvidenceRef(
            ref_type=RefType.NOTE,
            filing_year=self.filing_year,
            note_type=self.section_type,
            page_number=self.page_number,
            note_number=self.note_number,
            note_heading=self.note_heading,
            paragraph_index=self.paragraph_index,
            snippet=self.text[:200] if self.text else None,
            source_file=self.source_file,
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'company': self.company,
            'filing_year': self.filing_year,
            'source_file': self.source_file,
            'page_number': self.page_number,
            'note_heading': self.note_heading,
            'note_number': self.note_number,
            'paragraph_index': self.paragraph_index,
            'text': self.text,
            'section_type': self.section_type.value if isinstance(self.section_type, SectionType) else self.section_type,
        }


@dataclass
class SentimentYear:
    """Auditor sentiment analysis for a single year."""
    year: int
    score: float  # Higher = more hedged/risky
    category: Literal['CRITICAL', 'CONCERNING', 'NEUTRAL', 'STABLE']
    red_flag_count: int
    stable_count: int
    hedged_keywords_found: List[str] = field(default_factory=list)
    evidence_ref: Optional[EvidenceRef] = None
    text_length: int = 0
    
    # Flag if this is from real note parsing vs simulation
    is_real_data: bool = False


@dataclass
class SentimentTrend:
    """
    Auditor sentiment trend over multiple years.
    
    Tracks how auditor language changed over the filing history.
    """
    available: bool
    reason: Optional[str] = None  # Why unavailable if not
    years: Dict[int, SentimentYear] = field(default_factory=dict)
    
    # Trend analysis results
    is_deteriorating: bool = False
    deterioration_streak: int = 0
    spike_years: List[int] = field(default_factory=list)
    
    def add_year(self, sentiment_year: SentimentYear):
        """Add a year's sentiment data."""
        self.years[sentiment_year.year] = sentiment_year
    
    def get_sorted_years(self) -> List[int]:
        """Get years in chronological order."""
        return sorted(self.years.keys())
    
    def get_trend_description(self) -> str:
        """Generate a description of the sentiment trend."""
        if not self.available:
            return self.reason or "Auditor notes not available for analysis"
        
        if not self.years:
            return "No sentiment data available"
        
        sorted_years = self.get_sorted_years()
        if len(sorted_years) < 2:
            return "Insufficient data for trend analysis"
        
        first_score = self.years[sorted_years[0]].score
        last_score = self.years[sorted_years[-1]].score
        
        if last_score > first_score + 3:
            return "Auditor language has become MORE HEDGED over time"
        elif last_score < first_score - 3:
            return "Auditor language has become more stable over time"
        else:
            return "Auditor language sentiment relatively stable"


def create_statement_evidence(
    statement_type: str,
    line_item: str,
    year: int,
    value: Optional[float] = None
) -> EvidenceRef:
    """
    Factory function to create statement-based evidence reference.
    
    Args:
        statement_type: Type of statement (P&L, Balance Sheet, etc.)
        line_item: Specific line item name
        year: Filing year
        value: Optional numeric value
        
    Returns:
        EvidenceRef configured for statement reference
    """
    return EvidenceRef(
        ref_type=RefType.STATEMENT,
        filing_year=year,
        statement_type=statement_type,
        line_item=line_item,
        snippet=f"{line_item}: {value:,.0f}" if value is not None else None,
    )


def create_ratio_evidence(
    ratio_name: str,
    year: int,
    value: Optional[float] = None
) -> EvidenceRef:
    """
    Factory function to create ratio-based evidence reference.
    
    Args:
        ratio_name: Name of the financial ratio
        year: Filing year
        value: Optional ratio value
        
    Returns:
        EvidenceRef configured for ratio reference
    """
    return EvidenceRef(
        ref_type=RefType.RATIO,
        filing_year=year,
        line_item=ratio_name,
        snippet=f"{ratio_name}: {value:.2f}" if value is not None else None,
    )
