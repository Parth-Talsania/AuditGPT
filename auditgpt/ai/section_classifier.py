"""
Section classifier for AuditGPT.

Classifies extracted text chunks into canonical section types:
- auditor_note
- related_party
- mda (Management Discussion & Analysis)
- risk
- other
"""

from typing import Optional, List, Tuple
import re

from auditgpt.evidence.models import SectionType


class SectionClassifier:
    """
    Classifies text chunks into section types.
    
    Uses keyword and regex patterns for classification.
    Can optionally use embeddings for ambiguous cases.
    """
    
    # Auditor note patterns
    AUDITOR_PATTERNS = [
        r"independent\s*auditor",
        r"auditor['']?s?\s*report",
        r"basis\s*for\s*opinion",
        r"emphasis\s*of\s*matter",
        r"key\s*audit\s*matter",
        r"going\s*concern",
        r"material\s*uncertainty",
        r"qualified\s*opinion",
        r"auditor['']?s?\s*responsibility",
    ]
    
    # Related party patterns
    RPT_PATTERNS = [
        r"related\s*party",
        r"transaction.*with.*related",
        r"note.*related\s*party",
        r"disclosure.*related\s*party",
        r"key\s*management\s*personnel",
        r"subsidiary.*transaction",
        r"holding\s*company.*transaction",
    ]
    
    # MD&A patterns
    MDA_PATTERNS = [
        r"management\s*discussion",
        r"management['']?s?\s*discussion",
        r"md\s*&\s*a",
        r"business\s*overview",
        r"operational\s*review",
        r"financial\s*review",
        r"outlook",
        r"strategy.*going\s*forward",
    ]
    
    # Risk patterns
    RISK_PATTERNS = [
        r"risk\s*factor",
        r"risk\s*management",
        r"principal\s*risk",
        r"financial\s*risk",
        r"operational\s*risk",
        r"market\s*risk",
        r"credit\s*risk",
        r"liquidity\s*risk",
    ]
    
    def __init__(self):
        self._compile_patterns()
    
    def _compile_patterns(self):
        """Compile regex patterns for efficiency."""
        self._auditor_re = re.compile(
            '|'.join(self.AUDITOR_PATTERNS),
            re.IGNORECASE
        )
        self._rpt_re = re.compile(
            '|'.join(self.RPT_PATTERNS),
            re.IGNORECASE
        )
        self._mda_re = re.compile(
            '|'.join(self.MDA_PATTERNS),
            re.IGNORECASE
        )
        self._risk_re = re.compile(
            '|'.join(self.RISK_PATTERNS),
            re.IGNORECASE
        )
    
    def classify(self, text: str, heading: Optional[str] = None) -> SectionType:
        """
        Classify text into a section type.
        
        Args:
            text: The text content to classify
            heading: Optional section heading for additional context
            
        Returns:
            SectionType classification
        """
        # Combine heading and text for analysis
        combined = f"{heading or ''} {text}"
        
        # Score each category
        scores = self._calculate_scores(combined)
        
        # Return highest scoring category
        if scores['auditor'] > 0:
            return SectionType.AUDITOR_NOTE
        elif scores['rpt'] > 0:
            return SectionType.RELATED_PARTY
        elif scores['mda'] > 0:
            return SectionType.MDA
        elif scores['risk'] > 0:
            return SectionType.RISK
        else:
            return SectionType.OTHER
    
    def classify_with_confidence(
        self,
        text: str,
        heading: Optional[str] = None
    ) -> Tuple[SectionType, float]:
        """
        Classify text with confidence score.
        
        Args:
            text: The text content to classify
            heading: Optional section heading
            
        Returns:
            Tuple of (SectionType, confidence)
        """
        combined = f"{heading or ''} {text}"
        scores = self._calculate_scores(combined)
        
        # Get max score
        max_category = max(scores, key=scores.get)
        max_score = scores[max_category]
        
        # Calculate confidence based on score and relative strength
        total_score = sum(scores.values())
        if total_score == 0:
            return SectionType.OTHER, 0.3
        
        confidence = max_score / (total_score + 1)  # +1 to dampen
        confidence = min(confidence, 0.95)  # Cap at 95%
        
        category_map = {
            'auditor': SectionType.AUDITOR_NOTE,
            'rpt': SectionType.RELATED_PARTY,
            'mda': SectionType.MDA,
            'risk': SectionType.RISK,
        }
        
        section_type = category_map.get(max_category, SectionType.OTHER)
        
        return section_type, confidence
    
    def _calculate_scores(self, text: str) -> dict:
        """Calculate scores for each category."""
        scores = {
            'auditor': len(self._auditor_re.findall(text)),
            'rpt': len(self._rpt_re.findall(text)),
            'mda': len(self._mda_re.findall(text)),
            'risk': len(self._risk_re.findall(text)),
        }
        return scores
    
    def classify_heading(self, heading: str) -> Optional[SectionType]:
        """
        Classify based on heading alone.
        
        Args:
            heading: Section heading text
            
        Returns:
            SectionType if confident, None otherwise
        """
        heading_lower = heading.lower()
        
        # Strong heading indicators
        if any(kw in heading_lower for kw in ['auditor', 'audit report', 'basis for opinion']):
            return SectionType.AUDITOR_NOTE
        
        if any(kw in heading_lower for kw in ['related party', 'rpt']):
            return SectionType.RELATED_PARTY
        
        if any(kw in heading_lower for kw in ['management discussion', 'md&a', 'mda']):
            return SectionType.MDA
        
        if any(kw in heading_lower for kw in ['risk factor', 'risk management']):
            return SectionType.RISK
        
        return None
    
    def extract_note_number(self, text: str) -> Optional[str]:
        """
        Extract note number from text.
        
        Looks for patterns like "Note 25", "Note No. 25", etc.
        """
        patterns = [
            r"note\s*(?:no\.?\s*)?(\d+)",
            r"note\s*([a-z]+)",  # Note A, Note B
            r"schedule\s*(\d+|[a-z]+)",
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return match.group(1)
        
        return None
