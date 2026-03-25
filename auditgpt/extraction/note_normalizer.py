"""
Note normalizer for AuditGPT.

Maps variant headings across different companies/years to canonical section types.
"""

from typing import Optional, Tuple, Dict
import re

from auditgpt.evidence.models import SectionType


class NoteNormalizer:
    """
    Normalizes note headings to canonical types.
    
    Handles variations in how companies label their sections.
    """
    
    # Heading variations mapped to canonical types
    HEADING_MAPPINGS: Dict[str, SectionType] = {
        # Auditor report variations
        "independent auditor's report": SectionType.AUDITOR_NOTE,
        "independent auditors' report": SectionType.AUDITOR_NOTE,
        "auditor's report": SectionType.AUDITOR_NOTE,
        "auditors' report": SectionType.AUDITOR_NOTE,
        "report of the auditors": SectionType.AUDITOR_NOTE,
        "audit report": SectionType.AUDITOR_NOTE,
        "basis for opinion": SectionType.AUDITOR_NOTE,
        "basis of opinion": SectionType.AUDITOR_NOTE,
        "key audit matters": SectionType.AUDITOR_NOTE,
        "key audit matter": SectionType.AUDITOR_NOTE,
        "emphasis of matter": SectionType.AUDITOR_NOTE,
        "material uncertainty": SectionType.AUDITOR_NOTE,
        "going concern": SectionType.AUDITOR_NOTE,
        
        # Related party variations
        "related party transactions": SectionType.RELATED_PARTY,
        "related party disclosures": SectionType.RELATED_PARTY,
        "transactions with related parties": SectionType.RELATED_PARTY,
        "disclosure of related party": SectionType.RELATED_PARTY,
        "rpt disclosure": SectionType.RELATED_PARTY,
        "key management personnel": SectionType.RELATED_PARTY,
        "kmp remuneration": SectionType.RELATED_PARTY,
        
        # MD&A variations
        "management discussion and analysis": SectionType.MDA,
        "management's discussion and analysis": SectionType.MDA,
        "management discussion & analysis": SectionType.MDA,
        "mda": SectionType.MDA,
        "md&a": SectionType.MDA,
        "business overview": SectionType.MDA,
        "operational review": SectionType.MDA,
        "financial review": SectionType.MDA,
        "directors' report": SectionType.MDA,
        "board's report": SectionType.MDA,
        
        # Risk variations
        "risk factors": SectionType.RISK,
        "principal risks": SectionType.RISK,
        "risk management": SectionType.RISK,
        "financial risk management": SectionType.RISK,
        "risks and concerns": SectionType.RISK,
        "risk mitigation": SectionType.RISK,
    }
    
    def __init__(self):
        # Build normalized lookup
        self._lookup = {
            self._normalize_key(k): v
            for k, v in self.HEADING_MAPPINGS.items()
        }
    
    def _normalize_key(self, text: str) -> str:
        """Normalize text for lookup."""
        # Lowercase, remove extra spaces, remove punctuation
        text = text.lower()
        text = re.sub(r'[^\w\s]', '', text)
        text = re.sub(r'\s+', ' ', text).strip()
        return text
    
    def normalize(self, heading: str) -> Tuple[SectionType, float]:
        """
        Normalize a heading to a canonical section type.
        
        Args:
            heading: The section heading to normalize
            
        Returns:
            Tuple of (SectionType, confidence)
        """
        normalized = self._normalize_key(heading)
        
        # Exact match
        if normalized in self._lookup:
            return self._lookup[normalized], 1.0
        
        # Partial match
        for key, section_type in self._lookup.items():
            if key in normalized or normalized in key:
                return section_type, 0.8
        
        # Keyword matching
        section_type = self._keyword_match(normalized)
        if section_type != SectionType.OTHER:
            return section_type, 0.6
        
        return SectionType.OTHER, 0.3
    
    def _keyword_match(self, text: str) -> SectionType:
        """Match based on keywords."""
        keywords = {
            SectionType.AUDITOR_NOTE: ['audit', 'auditor', 'opinion', 'basis'],
            SectionType.RELATED_PARTY: ['related', 'party', 'transaction', 'rpt'],
            SectionType.MDA: ['management', 'discussion', 'analysis', 'review'],
            SectionType.RISK: ['risk', 'exposure', 'mitigation'],
        }
        
        for section_type, kws in keywords.items():
            matches = sum(1 for kw in kws if kw in text)
            if matches >= 2:
                return section_type
        
        return SectionType.OTHER
    
    def extract_note_number(self, heading: str) -> Optional[str]:
        """
        Extract note number from heading.
        
        Handles formats like:
        - "Note 25 - Related Party"
        - "Note No. 25"
        - "25. Related Party Transactions"
        - "Schedule VI"
        """
        patterns = [
            r'note\s*(?:no\.?\s*)?(\d+)',
            r'^(\d+)\.\s',
            r'schedule\s*([ivxlc]+|\d+)',
            r'annexure\s*([a-z]|\d+)',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, heading, re.IGNORECASE)
            if match:
                return match.group(1).upper()
        
        return None
    
    def is_continuation(self, prev_heading: str, curr_heading: str) -> bool:
        """
        Check if current heading is a continuation of previous section.
        
        Useful for multi-page sections.
        """
        # "Continued" patterns
        if re.search(r'cont[\'i]?n?u?e?d?\.?$', curr_heading, re.IGNORECASE):
            return True
        
        # Same note number
        prev_note = self.extract_note_number(prev_heading)
        curr_note = self.extract_note_number(curr_heading)
        
        if prev_note and curr_note and prev_note == curr_note:
            return True
        
        return False
    
    def get_canonical_heading(self, section_type: SectionType) -> str:
        """Get the canonical heading for a section type."""
        canonical = {
            SectionType.AUDITOR_NOTE: "Independent Auditor's Report",
            SectionType.RELATED_PARTY: "Related Party Transactions",
            SectionType.MDA: "Management Discussion and Analysis",
            SectionType.RISK: "Risk Management",
            SectionType.OTHER: "Other",
        }
        return canonical.get(section_type, "Unknown Section")
