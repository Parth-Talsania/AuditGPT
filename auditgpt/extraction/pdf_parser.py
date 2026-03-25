"""
PDF parser for AuditGPT annual report extraction.

Hybrid parser using:
- Primary: PyMuPDF (fitz) for text extraction
- Fallback: OCR (pytesseract) for scanned pages

Extracts note chunks with metadata including page numbers.
"""

from typing import List, Optional, Dict, Any
from dataclasses import dataclass
import os
import re

from auditgpt.evidence.models import NoteChunk, SectionType
from auditgpt.extraction.section_detector import SectionDetector


@dataclass
class PageContent:
    """Content extracted from a single page."""
    page_number: int
    text: str
    has_text: bool
    is_scanned: bool = False


class PDFParser:
    """
    Hybrid PDF parser for annual reports.
    
    Extracts text with page-level metadata for proper citations.
    """
    
    def __init__(self, use_ocr_fallback: bool = True):
        """
        Initialize the PDF parser.
        
        Args:
            use_ocr_fallback: Whether to use OCR for scanned pages
        """
        self.use_ocr_fallback = use_ocr_fallback
        self._section_detector = SectionDetector()
        self._fitz_available = self._check_fitz()
        self._ocr_available = self._check_ocr()
    
    def _check_fitz(self) -> bool:
        """Check if PyMuPDF is available."""
        try:
            import fitz
            return True
        except ImportError:
            return False
    
    def _check_ocr(self) -> bool:
        """Check if OCR dependencies are available."""
        try:
            import pytesseract
            from PIL import Image
            return True
        except ImportError:
            return False
    
    def parse(
        self,
        pdf_path: str,
        company: str,
        filing_year: int,
    ) -> List[NoteChunk]:
        """
        Parse a PDF and extract note chunks.
        
        Args:
            pdf_path: Path to the PDF file
            company: Company ticker/name
            filing_year: Fiscal year of the filing
            
        Returns:
            List of NoteChunk objects with section classifications
        """
        if not os.path.exists(pdf_path):
            raise FileNotFoundError(f"PDF not found: {pdf_path}")
        
        # Extract pages
        pages = self._extract_pages(pdf_path)
        
        if not pages:
            return []
        
        # Process pages into chunks
        chunks = self._process_pages(
            pages=pages,
            company=company,
            filing_year=filing_year,
            source_file=pdf_path,
        )
        
        return chunks
    
    def _extract_pages(self, pdf_path: str) -> List[PageContent]:
        """Extract content from all pages."""
        pages = []
        
        if self._fitz_available:
            pages = self._extract_with_fitz(pdf_path)
        else:
            # Fallback to pdfplumber if available
            pages = self._extract_with_pdfplumber(pdf_path)
        
        # OCR fallback for scanned pages
        if self.use_ocr_fallback and self._ocr_available:
            for page in pages:
                if not page.has_text or len(page.text.strip()) < 100:
                    ocr_text = self._ocr_page(pdf_path, page.page_number)
                    if ocr_text:
                        page.text = ocr_text
                        page.is_scanned = True
                        page.has_text = True
        
        return pages
    
    def _extract_with_fitz(self, pdf_path: str) -> List[PageContent]:
        """Extract text using PyMuPDF."""
        import fitz
        
        pages = []
        doc = fitz.open(pdf_path)
        
        for page_num in range(len(doc)):
            page = doc[page_num]
            text = page.get_text()
            
            pages.append(PageContent(
                page_number=page_num + 1,  # 1-indexed
                text=text,
                has_text=len(text.strip()) > 50,
            ))
        
        doc.close()
        return pages
    
    def _extract_with_pdfplumber(self, pdf_path: str) -> List[PageContent]:
        """Extract text using pdfplumber."""
        try:
            import pdfplumber
            
            pages = []
            with pdfplumber.open(pdf_path) as pdf:
                for i, page in enumerate(pdf.pages):
                    text = page.extract_text() or ""
                    pages.append(PageContent(
                        page_number=i + 1,
                        text=text,
                        has_text=len(text.strip()) > 50,
                    ))
            
            return pages
        except ImportError:
            return []
    
    def _ocr_page(self, pdf_path: str, page_number: int) -> Optional[str]:
        """OCR a specific page."""
        try:
            import fitz
            import pytesseract
            from PIL import Image
            import io
            
            doc = fitz.open(pdf_path)
            page = doc[page_number - 1]
            
            # Render page to image
            mat = fitz.Matrix(2, 2)  # 2x zoom for better OCR
            pix = page.get_pixmap(matrix=mat)
            
            # Convert to PIL Image
            img_data = pix.tobytes("png")
            img = Image.open(io.BytesIO(img_data))
            
            # OCR
            text = pytesseract.image_to_string(img)
            
            doc.close()
            return text
            
        except Exception:
            return None
    
    def _process_pages(
        self,
        pages: List[PageContent],
        company: str,
        filing_year: int,
        source_file: str,
    ) -> List[NoteChunk]:
        """Process pages into note chunks."""
        chunks = []
        current_section: Optional[SectionType] = None
        current_heading: Optional[str] = None
        paragraph_idx = 0
        
        for page in pages:
            if not page.has_text:
                continue
            
            # Detect sections in page
            sections = self._section_detector.detect_sections(page.text)
            
            for section_info in sections:
                section_type = section_info['type']
                heading = section_info.get('heading')
                text = section_info['text']
                
                if section_type != current_section:
                    current_section = section_type
                    current_heading = heading
                    paragraph_idx = 0
                
                # Split into paragraphs
                paragraphs = self._split_into_paragraphs(text)
                
                for para in paragraphs:
                    if len(para.strip()) < 50:
                        continue
                    
                    chunk = NoteChunk(
                        company=company,
                        filing_year=filing_year,
                        source_file=source_file,
                        page_number=page.page_number,
                        text=para.strip(),
                        section_type=section_type,
                        note_heading=current_heading,
                        note_number=self._extract_note_number(current_heading),
                        paragraph_index=paragraph_idx,
                    )
                    
                    chunks.append(chunk)
                    paragraph_idx += 1
        
        return chunks
    
    def _split_into_paragraphs(self, text: str) -> List[str]:
        """Split text into paragraphs."""
        # Split on double newlines or multiple spaces indicating paragraph breaks
        paragraphs = re.split(r'\n\s*\n|\n{2,}', text)
        return [p.strip() for p in paragraphs if p.strip()]
    
    def _extract_note_number(self, heading: Optional[str]) -> Optional[str]:
        """Extract note number from heading."""
        if not heading:
            return None
        
        # Look for patterns like "Note 25", "Note No. 25"
        match = re.search(r'note\s*(?:no\.?\s*)?(\d+)', heading, re.IGNORECASE)
        if match:
            return match.group(1)
        
        return None
    
    def get_parser_status(self) -> Dict[str, bool]:
        """Get status of parser dependencies."""
        return {
            'fitz_available': self._fitz_available,
            'ocr_available': self._ocr_available,
            'pdfplumber_available': self._check_pdfplumber(),
        }
    
    def _check_pdfplumber(self) -> bool:
        """Check if pdfplumber is available."""
        try:
            import pdfplumber
            return True
        except ImportError:
            return False
