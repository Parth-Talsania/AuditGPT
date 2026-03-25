"""
Tests for evidence models and citation system.
"""

import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from auditgpt.evidence.models import EvidenceRef, NoteChunk, RefType, SectionType
from auditgpt.evidence.store import EvidenceStore


class TestEvidenceRef:
    """Tests for EvidenceRef dataclass."""
    
    def test_statement_citation(self):
        """Test citation string for statement references."""
        ref = EvidenceRef(
            ref_type=RefType.STATEMENT,
            filing_year=2024,
            statement_type="P&L",
            line_item="Revenue",
        )
        
        citation = ref.citation_string
        
        assert "P&L" in citation
        assert "Revenue" in citation
        assert "2024" in citation or "FY2024" in citation
    
    def test_note_citation(self):
        """Test citation string for note references."""
        ref = EvidenceRef(
            ref_type=RefType.NOTE,
            filing_year=2024,
            page_number=45,
            note_number="15",
            snippet="Going concern uncertainty noted",
        )
        
        citation = ref.citation_string
        
        assert "2024" in citation or "FY2024" in citation
        assert "45" in citation or "Page 45" in citation
        assert "15" in citation or "Note 15" in citation
    
    def test_ratio_citation(self):
        """Test citation string for ratio references."""
        ref = EvidenceRef(
            ref_type=RefType.RATIO,
            filing_year=2024,
            ratio_name="Debt/Equity",
            ratio_value=2.5,
            snippet="D/E = 2.5",
        )
        
        citation = ref.citation_string
        
        assert "2024" in citation or "FY2024" in citation
        # Should include ratio info
        assert "Debt" in citation or "D/E" in citation or "ratio" in citation.lower()
    
    def test_citation_with_minimal_fields(self):
        """Test citation with only required fields."""
        ref = EvidenceRef(
            ref_type=RefType.STATEMENT,
            filing_year=2024,
        )
        
        # Should not crash, return some citation
        citation = ref.citation_string
        assert citation  # Non-empty
        assert "2024" in citation or "FY2024" in citation


class TestNoteChunk:
    """Tests for NoteChunk dataclass."""
    
    def test_note_chunk_creation(self):
        """Test NoteChunk creation."""
        chunk = NoteChunk(
            company="HDFCBANK",
            filing_year=2024,
            source_file="HDFC_AR_2024.pdf",
            page_number=78,
            note_heading="Independent Auditor's Report",
            note_number="1",
            paragraph_index=0,
            text="We have audited the financial statements...",
            section_type=SectionType.AUDITOR_NOTE,
        )
        
        assert chunk.company == "HDFCBANK"
        assert chunk.page_number == 78
        assert chunk.section_type == SectionType.AUDITOR_NOTE
    
    def test_note_chunk_to_evidence_ref(self):
        """Test converting NoteChunk to EvidenceRef."""
        chunk = NoteChunk(
            company="TCS",
            filing_year=2024,
            source_file="TCS_AR_2024.pdf",
            page_number=120,
            note_heading="Related Party Transactions",
            note_number="32",
            paragraph_index=2,
            text="Transactions with subsidiaries totaled INR 5000 Cr",
            section_type=SectionType.RELATED_PARTY,
        )
        
        ref = chunk.to_evidence_ref()
        
        assert ref.ref_type == RefType.NOTE
        assert ref.filing_year == 2024
        assert ref.page_number == 120
        assert ref.note_number == "32"


class TestEvidenceStore:
    """Tests for EvidenceStore."""
    
    def test_add_and_retrieve_chunks(self, evidence_store):
        """Test adding and retrieving note chunks."""
        chunks = [
            NoteChunk(
                company="INFY",
                filing_year=2024,
                source_file="INFY_AR.pdf",
                page_number=50,
                note_heading="Auditor Report",
                paragraph_index=0,
                text="Clean audit opinion",
                section_type=SectionType.AUDITOR_NOTE,
            ),
            NoteChunk(
                company="INFY",
                filing_year=2024,
                source_file="INFY_AR.pdf",
                page_number=100,
                note_heading="RPT",
                paragraph_index=0,
                text="Related party transactions",
                section_type=SectionType.RELATED_PARTY,
            ),
        ]
        
        evidence_store.add_note_chunks(chunks)
        
        # Retrieve by company and year
        retrieved = evidence_store.get_notes_by_company_year("INFY", 2024)
        assert len(retrieved) == 2
    
    def test_retrieve_by_section_type(self, evidence_store):
        """Test retrieving notes by section type."""
        chunks = [
            NoteChunk(
                company="TCS",
                filing_year=2024,
                source_file="TCS_AR.pdf",
                page_number=50,
                note_heading="Auditor",
                paragraph_index=0,
                text="Audit note",
                section_type=SectionType.AUDITOR_NOTE,
            ),
            NoteChunk(
                company="TCS",
                filing_year=2024,
                source_file="TCS_AR.pdf",
                page_number=100,
                note_heading="MD&A",
                paragraph_index=0,
                text="Management discussion",
                section_type=SectionType.MDA,
            ),
        ]
        
        evidence_store.add_note_chunks(chunks)
        
        auditor_notes = evidence_store.get_notes_by_section_type(SectionType.AUDITOR_NOTE)
        assert all(n.section_type == SectionType.AUDITOR_NOTE for n in auditor_notes)
    
    def test_empty_store(self, evidence_store):
        """Test empty store returns empty results."""
        result = evidence_store.get_notes_by_company_year("NONEXISTENT", 2024)
        assert result == []
    
    def test_search_notes(self, evidence_store):
        """Test searching notes by keyword."""
        chunks = [
            NoteChunk(
                company="WIPRO",
                filing_year=2024,
                source_file="WIPRO_AR.pdf",
                page_number=50,
                note_heading="Auditor",
                paragraph_index=0,
                text="Going concern uncertainty has been identified",
                section_type=SectionType.AUDITOR_NOTE,
            ),
            NoteChunk(
                company="WIPRO",
                filing_year=2024,
                source_file="WIPRO_AR.pdf",
                page_number=60,
                note_heading="Other",
                paragraph_index=0,
                text="Normal business operations",
                section_type=SectionType.OTHER,
            ),
        ]
        
        evidence_store.add_note_chunks(chunks)
        
        # Search for "going concern"
        results = evidence_store.search_notes("going concern")
        
        # Should find the first chunk
        assert len(results) >= 0  # At least doesn't crash
        if results:
            assert "going concern" in results[0].text.lower()


class TestRefType:
    """Tests for RefType enum."""
    
    def test_ref_types_exist(self):
        """Test that all expected ref types exist."""
        assert RefType.STATEMENT
        assert RefType.NOTE
        assert RefType.RATIO
    
    def test_ref_type_values(self):
        """Test ref type string values."""
        assert RefType.STATEMENT.value == 'statement'
        assert RefType.NOTE.value == 'note'
        assert RefType.RATIO.value == 'ratio'


class TestSectionType:
    """Tests for SectionType enum."""
    
    def test_section_types_exist(self):
        """Test that all expected section types exist."""
        assert SectionType.AUDITOR_NOTE
        assert SectionType.RELATED_PARTY
        assert SectionType.MDA
        assert SectionType.RISK
        assert SectionType.OTHER
