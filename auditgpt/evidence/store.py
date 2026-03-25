"""
Evidence store for AuditGPT.

Manages storage and retrieval of evidence chunks from annual reports.
"""

from typing import List, Dict, Optional, Any
from collections import defaultdict
import json
import os

from auditgpt.evidence.models import NoteChunk, EvidenceRef, SectionType


class EvidenceStore:
    """
    Storage and retrieval system for evidence chunks.
    
    Supports:
    - Adding note chunks from PDF parsing
    - Retrieval by company, year, section type
    - Simple text search for RAG
    """
    
    def __init__(self, cache_dir: Optional[str] = None):
        """
        Initialize the evidence store.
        
        Args:
            cache_dir: Optional directory for persistent storage
        """
        self._chunks: List[NoteChunk] = []
        self._by_company: Dict[str, List[NoteChunk]] = defaultdict(list)
        self._by_year: Dict[int, List[NoteChunk]] = defaultdict(list)
        self._by_section: Dict[SectionType, List[NoteChunk]] = defaultdict(list)
        self._cache_dir = cache_dir
        
        if cache_dir:
            os.makedirs(cache_dir, exist_ok=True)
    
    def add_note_chunk(self, chunk: NoteChunk):
        """Add a single note chunk to the store."""
        self._chunks.append(chunk)
        self._by_company[chunk.company].append(chunk)
        self._by_year[chunk.filing_year].append(chunk)
        self._by_section[chunk.section_type].append(chunk)
    
    def add_note_chunks(self, chunks: List[NoteChunk]):
        """Add multiple note chunks to the store."""
        for chunk in chunks:
            self.add_note_chunk(chunk)
    
    def get_notes_by_company(self, company: str) -> List[NoteChunk]:
        """Get all note chunks for a company."""
        return self._by_company.get(company, [])
    
    def get_notes_by_company_year(self, company: str, year: int) -> List[NoteChunk]:
        """Get note chunks for a specific company and year."""
        return [
            chunk for chunk in self._by_company.get(company, [])
            if chunk.filing_year == year
        ]
    
    def get_notes_by_section_type(self, section_type: SectionType) -> List[NoteChunk]:
        """Get all note chunks of a specific section type."""
        return self._by_section.get(section_type, [])
    
    def get_auditor_notes(self, company: str) -> List[NoteChunk]:
        """Get all auditor note chunks for a company."""
        return [
            chunk for chunk in self._by_company.get(company, [])
            if chunk.section_type == SectionType.AUDITOR_NOTE
        ]
    
    def get_rpt_notes(self, company: str) -> List[NoteChunk]:
        """Get all related-party transaction notes for a company."""
        return [
            chunk for chunk in self._by_company.get(company, [])
            if chunk.section_type == SectionType.RELATED_PARTY
        ]
    
    def get_mda_notes(self, company: str) -> List[NoteChunk]:
        """Get all MD&A notes for a company."""
        return [
            chunk for chunk in self._by_company.get(company, [])
            if chunk.section_type == SectionType.MDA
        ]
    
    def search_notes(self, query: str, limit: int = 10) -> List[NoteChunk]:
        """
        Simple keyword search over note chunks.
        
        For full RAG, use the HybridRetriever from ai module.
        
        Args:
            query: Search query string
            limit: Maximum results to return
            
        Returns:
            List of matching NoteChunks, sorted by relevance
        """
        query_lower = query.lower()
        query_terms = query_lower.split()
        
        scored_chunks = []
        for chunk in self._chunks:
            text_lower = chunk.text.lower()
            
            # Simple scoring: count matching terms
            score = sum(1 for term in query_terms if term in text_lower)
            
            # Boost for heading matches
            if chunk.note_heading:
                heading_lower = chunk.note_heading.lower()
                score += sum(2 for term in query_terms if term in heading_lower)
            
            if score > 0:
                scored_chunks.append((score, chunk))
        
        # Sort by score descending
        scored_chunks.sort(key=lambda x: x[0], reverse=True)
        
        return [chunk for _, chunk in scored_chunks[:limit]]
    
    def has_notes_for_company(self, company: str) -> bool:
        """Check if any notes exist for a company."""
        return company in self._by_company and len(self._by_company[company]) > 0
    
    def has_auditor_notes(self, company: str) -> bool:
        """Check if auditor notes exist for a company."""
        return any(
            chunk.section_type == SectionType.AUDITOR_NOTE
            for chunk in self._by_company.get(company, [])
        )
    
    def has_rpt_notes(self, company: str) -> bool:
        """Check if RPT notes exist for a company."""
        return any(
            chunk.section_type == SectionType.RELATED_PARTY
            for chunk in self._by_company.get(company, [])
        )
    
    def get_years_with_notes(self, company: str) -> List[int]:
        """Get list of years for which notes exist."""
        years = set()
        for chunk in self._by_company.get(company, []):
            years.add(chunk.filing_year)
        return sorted(years)
    
    def clear(self):
        """Clear all stored chunks."""
        self._chunks.clear()
        self._by_company.clear()
        self._by_year.clear()
        self._by_section.clear()
    
    def save_to_cache(self, company: str):
        """Save company's notes to cache file."""
        if not self._cache_dir:
            return
        
        chunks = self._by_company.get(company, [])
        if not chunks:
            return
        
        cache_file = os.path.join(self._cache_dir, f"{company}_notes.json")
        data = [chunk.to_dict() for chunk in chunks]
        
        with open(cache_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    
    def load_from_cache(self, company: str) -> bool:
        """
        Load company's notes from cache file.
        
        Returns:
            True if cache was found and loaded, False otherwise
        """
        if not self._cache_dir:
            return False
        
        cache_file = os.path.join(self._cache_dir, f"{company}_notes.json")
        if not os.path.exists(cache_file):
            return False
        
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            for item in data:
                chunk = NoteChunk(
                    company=item['company'],
                    filing_year=item['filing_year'],
                    source_file=item['source_file'],
                    page_number=item['page_number'],
                    text=item['text'],
                    section_type=SectionType(item['section_type']),
                    note_heading=item.get('note_heading'),
                    note_number=item.get('note_number'),
                    paragraph_index=item.get('paragraph_index', 0),
                )
                self.add_note_chunk(chunk)
            
            return True
        except Exception:
            return False
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get statistics about stored evidence."""
        return {
            'total_chunks': len(self._chunks),
            'companies': list(self._by_company.keys()),
            'years': sorted(self._by_year.keys()),
            'section_counts': {
                section.value: len(chunks)
                for section, chunks in self._by_section.items()
            },
        }
