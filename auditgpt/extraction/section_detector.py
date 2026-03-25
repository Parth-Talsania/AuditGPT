"""
Section detector for AuditGPT PDF extraction.

Detects and extracts specific sections from annual report text:
- Independent Auditor's Report
- Related Party Transactions
- Management Discussion & Analysis
- Risk Factors
"""

from typing import List, Dict, Any, Optional
import re

from auditgpt.evidence.models import SectionType


class SectionDetector:
    """
    Detects sections within annual report pages.
    
    Uses pattern matching to identify section boundaries.
    """
    
    # Section start patterns
    SECTION_PATTERNS = {
        SectionType.AUDITOR_NOTE: [
            r"(?:^|\n)INDEPENDENT\s+AUDITOR['']?S?\s+REPORT",
            r"(?:^|\n)AUDITOR['']?S?\s+REPORT",
            r"(?:^|\n)REPORT\s+ON\s+THE\s+AUDIT",
            r"(?:^|\n)BASIS\s+FOR\s+OPINION",
            r"(?:^|\n)KEY\s+AUDIT\s+MATTERS?",
            r"(?:^|\n)EMPHASIS\s+OF\s+MATTER",
        ],
        SectionType.RELATED_PARTY: [
            r"(?:^|\n)RELATED\s+PARTY\s+(?:TRANSACTIONS?|DISCLOSURES?)",
            r"(?:^|\n)NOTE\s+\d+[:\s]+RELATED\s+PARTY",
            r"(?:^|\n)TRANSACTIONS?\s+WITH\s+RELATED\s+PARTIES",
            r"(?:^|\n)DISCLOSURE\s+OF\s+RELATED\s+PARTY",
        ],
        SectionType.MDA: [
            r"(?:^|\n)MANAGEMENT['']?S?\s+DISCUSSION\s+AND\s+ANALYSIS",
            r"(?:^|\n)MANAGEMENT\s+DISCUSSION\s+&\s+ANALYSIS",
            r"(?:^|\n)MD\s*&\s*A",
            r"(?:^|\n)BUSINESS\s+OVERVIEW",
            r"(?:^|\n)OPERATIONAL\s+REVIEW",
        ],
        SectionType.RISK: [
            r"(?:^|\n)RISK\s+FACTORS?",
            r"(?:^|\n)PRINCIPAL\s+RISKS?",
            r"(?:^|\n)RISK\s+MANAGEMENT",
            r"(?:^|\n)FINANCIAL\s+RISK\s+MANAGEMENT",
        ],
    }
    
    # Section end patterns (generic)
    SECTION_END_PATTERNS = [
        r"(?:^|\n)(?:NOTE|NOTES)\s+(?:TO|ON)\s+",
        r"(?:^|\n)FOR\s+AND\s+ON\s+BEHALF\s+OF",
        r"(?:^|\n)(?:DIRECTOR|CHAIRMAN|CEO)['']?S?\s+(?:REPORT|SIGNATURE)",
        r"(?:^|\n)ANNEXURE",
        r"(?:^|\n)SCHEDULE\s+[A-Z0-9]+",
    ]
    
    def __init__(self):
        self._compile_patterns()
    
    def _compile_patterns(self):
        """Compile regex patterns for efficiency."""
        self._compiled_patterns = {}
        
        for section_type, patterns in self.SECTION_PATTERNS.items():
            self._compiled_patterns[section_type] = [
                re.compile(p, re.IGNORECASE | re.MULTILINE)
                for p in patterns
            ]
        
        self._end_patterns = [
            re.compile(p, re.IGNORECASE | re.MULTILINE)
            for p in self.SECTION_END_PATTERNS
        ]
    
    def detect_sections(self, text: str) -> List[Dict[str, Any]]:
        """
        Detect all sections in the text.
        
        Args:
            text: Page or document text
            
        Returns:
            List of dicts with 'type', 'heading', 'text', 'start_pos'
        """
        sections = []
        
        # Find all section starts
        section_starts = []
        
        for section_type, patterns in self._compiled_patterns.items():
            for pattern in patterns:
                for match in pattern.finditer(text):
                    section_starts.append({
                        'type': section_type,
                        'start': match.start(),
                        'heading': match.group().strip(),
                    })
        
        # Sort by position
        section_starts.sort(key=lambda x: x['start'])
        
        # Extract text for each section
        for i, section in enumerate(section_starts):
            start = section['start']
            
            # Find end (next section start or end of text)
            if i + 1 < len(section_starts):
                end = section_starts[i + 1]['start']
            else:
                end = len(text)
            
            # Check for section end patterns
            for end_pattern in self._end_patterns:
                match = end_pattern.search(text, start + 100, end)  # Start after heading
                if match:
                    end = min(end, match.start())
            
            section_text = text[start:end].strip()
            
            sections.append({
                'type': section['type'],
                'heading': section['heading'],
                'text': section_text,
                'start_pos': start,
            })
        
        # If no specific sections found, classify entire text
        if not sections:
            # Try to classify the whole text
            section_type = self._classify_text(text)
            sections.append({
                'type': section_type,
                'heading': None,
                'text': text,
                'start_pos': 0,
            })
        
        return sections
    
    def _classify_text(self, text: str) -> SectionType:
        """Classify text when no clear section markers found."""
        text_lower = text.lower()
        
        # Score each section type
        scores = {}
        
        keywords = {
            SectionType.AUDITOR_NOTE: [
                'audit', 'auditor', 'opinion', 'basis for', 'examination',
                'true and fair', 'material misstatement'
            ],
            SectionType.RELATED_PARTY: [
                'related party', 'transaction', 'subsidiary', 'holding company',
                'key management', 'director', 'compensation'
            ],
            SectionType.MDA: [
                'management', 'discussion', 'analysis', 'outlook', 'strategy',
                'performance', 'review', 'operational'
            ],
            SectionType.RISK: [
                'risk', 'exposure', 'mitigation', 'hedging', 'sensitivity',
                'credit risk', 'market risk', 'liquidity risk'
            ],
        }
        
        for section_type, kws in keywords.items():
            score = sum(1 for kw in kws if kw in text_lower)
            scores[section_type] = score
        
        if max(scores.values()) > 2:
            return max(scores, key=scores.get)
        
        return SectionType.OTHER
    
    def is_auditor_report(self, text: str) -> bool:
        """Check if text is part of auditor report."""
        for pattern in self._compiled_patterns[SectionType.AUDITOR_NOTE]:
            if pattern.search(text):
                return True
        return False
    
    def is_rpt_section(self, text: str) -> bool:
        """Check if text is part of related party section."""
        for pattern in self._compiled_patterns[SectionType.RELATED_PARTY]:
            if pattern.search(text):
                return True
        return False
    
    def extract_heading(self, text: str) -> Optional[str]:
        """Extract the main heading from text."""
        # Look for heading patterns
        heading_pattern = re.compile(
            r'^([A-Z][A-Z\s\-\']+(?:\s*\([^)]+\))?)(?:\n|$)',
            re.MULTILINE
        )
        
        match = heading_pattern.search(text[:500])  # First 500 chars
        if match:
            return match.group(1).strip()
        
        return None
