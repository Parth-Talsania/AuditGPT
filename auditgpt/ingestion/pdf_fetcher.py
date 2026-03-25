"""
Dynamic PDF Fetcher for Annual Reports.

Implements a tiered approach to acquire auditor notes and RPT data:
- Tier 1: Check qualitative cache (instant)
- Tier 2: Check local PDF directory (fast)
- Tier 3: Fetch from BSE/Screener (automated but slower)
- Tier 4: Fall back to proxy sentiment

This solves the problem of needing PDFs for any company ticker
while maintaining the same flexibility as screener.in data.
"""

import os
import re
import json
import requests
import urllib3
from typing import Dict, Optional, Any, Tuple, List
from datetime import datetime
import time

# Disable SSL warnings for BSE API (their certificate has issues)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Try to import PDF parsing libraries
try:
    import PyPDF2
    PYPDF2_AVAILABLE = True
except ImportError:
    PYPDF2_AVAILABLE = False

try:
    import fitz  # PyMuPDF
    PYMUPDF_AVAILABLE = True
except ImportError:
    PYMUPDF_AVAILABLE = False


class AnnualReportFetcher:
    """
    Fetches and caches annual report PDFs from BSE/NSE.
    
    Provides dynamic PDF acquisition matching screener.in's flexibility.
    """
    
    # BSE Scrip Code mapping (commonly queried companies)
    # This can be expanded or fetched dynamically
    SCRIP_CODES = {
        'YESBANK': '532648',
        'HDFCBANK': '500180',
        'ICICIBANK': '532174',
        'SBIN': '500112',
        'AXISBANK': '532215',
        'KOTAKBANK': '500247',
        'INDUSINDBK': '532187',
        'BANKBARODA': '532134',
        'PNB': '532461',
        'CANBK': '532483',
        'RELIANCE': '500325',
        'TCS': '532540',
        'INFY': '500209',
        'WIPRO': '507685',
        'HCLTECH': '532281',
        'TECHM': '532755',
        'LT': '500510',
        'BAJFINANCE': '500034',
        'BAJAJFINSV': '532978',
        'HDFC': '500010',
        'DLF': '532868',
        'GODREJPROP': '533150',
    }
    
    def __init__(
        self,
        cache_dir: str = ".cache/auditgpt/pdfs",
        qualitative_cache_file: str = "demo_qualitative_cache.json",
    ):
        """
        Initialize the PDF fetcher.
        
        Args:
            cache_dir: Directory to store downloaded PDFs
            qualitative_cache_file: Path to qualitative cache JSON
        """
        self.cache_dir = cache_dir
        self.qualitative_cache_file = qualitative_cache_file
        self._qualitative_cache = None
        
        # Create cache directory if needed
        os.makedirs(cache_dir, exist_ok=True)
        
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }
    
    def fetch_notes(
        self,
        ticker: str,
        years: Optional[List[int]] = None,
    ) -> Dict[str, Any]:
        """
        Fetch auditor notes and RPT notes using tiered approach.
        
        Args:
            ticker: Company ticker symbol
            years: List of years to fetch (default: last 3 years)
            
        Returns:
            Dict with notes data and source information
        """
        ticker = ticker.upper()
        if years is None:
            current_year = datetime.now().year
            years = [current_year, current_year - 1, current_year - 2]
        
        result = {
            'ticker': ticker,
            'auditor_notes': {},
            'rpt_notes': {},
            'source': None,
            'available': False,
            'fetch_method': None,
        }
        
        # Tier 1: Check qualitative cache
        cached = self._check_qualitative_cache(ticker)
        if cached:
            result.update(cached)
            result['source'] = 'qualitative_cache'
            result['fetch_method'] = 'Tier 1: Qualitative Cache'
            result['available'] = True
            return result
        
        # Tier 2: Check local PDF directory
        local_result = self._check_local_pdfs(ticker, years)
        if local_result['available']:
            result.update(local_result)
            result['source'] = 'local_pdf'
            result['fetch_method'] = 'Tier 2: Local PDF Directory'
            return result
        
        # Tier 3: Attempt BSE/Screener fetch
        bse_result = self._fetch_from_bse(ticker, years)
        if bse_result['available']:
            result.update(bse_result)
            result['source'] = 'bse_fetch'
            result['fetch_method'] = 'Tier 3: BSE Auto-Fetch'
            # Cache for future use
            self._update_qualitative_cache(ticker, bse_result)
            return result
        
        # Tier 4: Return unavailable with clear disclosure
        result['source'] = 'unavailable'
        result['fetch_method'] = 'Tier 4: Not Available'
        result['reason'] = self._get_unavailability_reason(ticker)
        result['recommendation'] = self._get_recommendation(ticker)
        
        return result
    
    def _check_qualitative_cache(self, ticker: str) -> Optional[Dict]:
        """Tier 1: Check qualitative cache."""
        if self._qualitative_cache is None:
            if os.path.exists(self.qualitative_cache_file):
                try:
                    with open(self.qualitative_cache_file, 'r') as f:
                        self._qualitative_cache = json.load(f)
                except (json.JSONDecodeError, IOError):
                    self._qualitative_cache = {}
            else:
                self._qualitative_cache = {}
        
        if ticker in self._qualitative_cache:
            data = self._qualitative_cache[ticker]
            return {
                'auditor_notes': data.get('auditor_notes', {}),
                'rpt_notes': data.get('rpt_notes', {}),
                'available': bool(data.get('auditor_notes')),
            }
        return None
    
    def _check_local_pdfs(self, ticker: str, years: List[int]) -> Dict:
        """Tier 2: Check local PDF directory."""
        result = {
            'auditor_notes': {},
            'rpt_notes': {},
            'available': False,
        }
        
        # Look for PDFs matching pattern: TICKER_YYYY_annual_report.pdf
        for year in years:
            patterns = [
                f"{ticker}_{year}_annual_report.pdf",
                f"{ticker}_{year}.pdf",
                f"{ticker}_AR_{year}.pdf",
            ]
            
            for pattern in patterns:
                pdf_path = os.path.join(self.cache_dir, pattern)
                if os.path.exists(pdf_path):
                    notes = self._extract_notes_from_pdf(pdf_path, year)
                    if notes:
                        result['auditor_notes'][str(year)] = notes.get('auditor', '')
                        result['rpt_notes'][str(year)] = notes.get('rpt', '')
                        result['available'] = True
        
        return result
    
    def _fetch_from_bse(self, ticker: str, years: List[int]) -> Dict:
        """Tier 3: Fetch from BSE India."""
        result = {
            'auditor_notes': {},
            'rpt_notes': {},
            'available': False,
        }
        
        scrip_code = self.SCRIP_CODES.get(ticker)
        if not scrip_code:
            # Try to fetch scrip code dynamically
            scrip_code = self._lookup_scrip_code(ticker)
        
        if not scrip_code:
            return result
        
        try:
            # BSE announcements API (using verify=False due to BSE SSL cert issues)
            url = f"https://api.bseindia.com/BseIndiaAPI/api/AnnGetData/w?strCat=Annual%20Report&strPrevDate=&strScrip={scrip_code}&strSearch=P&strToDate=&strType=C"
            
            response = requests.get(url, headers=self.headers, timeout=15, verify=False)
            if response.status_code == 200:
                data = response.json()
                
                if data and 'Table' in data:
                    for item in data['Table'][:5]:  # Latest 5 reports
                        pdf_url = item.get('ATTACHMENTNAME', '')
                        news_date = item.get('NEWS_DT', '')
                        
                        if pdf_url and news_date:
                            # Extract year from date
                            year = self._extract_year_from_date(news_date)
                            if year in years:
                                # Download and parse PDF
                                notes = self._download_and_parse_pdf(pdf_url, ticker, year)
                                if notes:
                                    result['auditor_notes'][str(year)] = notes.get('auditor', '')
                                    result['rpt_notes'][str(year)] = notes.get('rpt', '')
                                    result['available'] = True
        except Exception as e:
            print(f"[PDFFetcher] BSE fetch failed for {ticker}: {e}")
        
        return result
    
    def _lookup_scrip_code(self, ticker: str) -> Optional[str]:
        """Dynamically lookup BSE scrip code for a ticker."""
        try:
            url = f"https://api.bseindia.com/BseIndiaAPI/api/ListofScripData/w?Group=&Scripcode=&industry=&segment=Equity&status=Active"
            response = requests.get(url, headers=self.headers, timeout=10, verify=False)
            
            if response.status_code == 200:
                data = response.json()
                for item in data:
                    if item.get('scrip_id', '').upper() == ticker:
                        return item.get('SCRIP_CD')
        except Exception:
            pass
        return None
    
    def _download_and_parse_pdf(
        self,
        pdf_url: str,
        ticker: str,
        year: int
    ) -> Optional[Dict]:
        """Download PDF and extract notes."""
        try:
            # Download PDF (verify=False for BSE)
            response = requests.get(pdf_url, headers=self.headers, timeout=60, verify=False)
            if response.status_code != 200:
                return None
            
            # Save to cache
            filename = f"{ticker}_{year}_annual_report.pdf"
            filepath = os.path.join(self.cache_dir, filename)
            
            with open(filepath, 'wb') as f:
                f.write(response.content)
            
            # Parse PDF
            return self._extract_notes_from_pdf(filepath, year)
            
        except Exception as e:
            print(f"[PDFFetcher] Download failed: {e}")
            return None
    
    def _extract_notes_from_pdf(self, pdf_path: str, year: int) -> Optional[Dict]:
        """Extract auditor notes and RPT notes from PDF."""
        if not PYMUPDF_AVAILABLE and not PYPDF2_AVAILABLE:
            return None
        
        try:
            text = ""
            
            if PYMUPDF_AVAILABLE:
                doc = fitz.open(pdf_path)
                for page in doc:
                    text += page.get_text()
                doc.close()
            elif PYPDF2_AVAILABLE:
                with open(pdf_path, 'rb') as f:
                    reader = PyPDF2.PdfReader(f)
                    for page in reader.pages:
                        text += page.extract_text() or ""
            
            if not text:
                return None
            
            # Extract auditor's report section
            auditor_note = self._extract_auditor_section(text)
            
            # Extract RPT section
            rpt_note = self._extract_rpt_section(text)
            
            return {
                'auditor': auditor_note,
                'rpt': rpt_note,
            }
            
        except Exception as e:
            print(f"[PDFFetcher] PDF parsing failed: {e}")
            return None
    
    def _extract_auditor_section(self, text: str) -> str:
        """Extract auditor's report section from PDF text."""
        # Common patterns for auditor's report
        patterns = [
            r"INDEPENDENT AUDITOR['\u2019]?S REPORT.*?(?=ANNEXURE|BALANCE SHEET|STATEMENT OF)",
            r"AUDITOR['\u2019]?S REPORT.*?(?=ANNEXURE|BALANCE SHEET)",
            r"Report on the (?:Standalone )?Financial Statements.*?(?=Annexure|Report on)",
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
            if match:
                extracted = match.group(0)
                # Clean and truncate
                extracted = re.sub(r'\s+', ' ', extracted)
                return extracted[:2000]  # Limit to 2000 chars
        
        return ""
    
    def _extract_rpt_section(self, text: str) -> str:
        """Extract related party transactions section from PDF text."""
        patterns = [
            r"RELATED PARTY (?:TRANSACTIONS|DISCLOSURES).*?(?=\d+\.\s+[A-Z]|\n\n\n)",
            r"Note \d+[:\s]+Related Party.*?(?=Note \d+|$)",
            r"Transactions with Related Parties.*?(?=\n\n\n|\d+\.\s+[A-Z])",
        ]
        
        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE | re.DOTALL)
            if match:
                extracted = match.group(0)
                extracted = re.sub(r'\s+', ' ', extracted)
                return extracted[:2000]
        
        return ""
    
    def _extract_year_from_date(self, date_str: str) -> int:
        """Extract year from BSE date format."""
        try:
            # BSE format: "DD-Mon-YYYY" or similar
            match = re.search(r'(\d{4})', date_str)
            if match:
                return int(match.group(1))
        except Exception:
            pass
        return datetime.now().year
    
    def _update_qualitative_cache(self, ticker: str, data: Dict):
        """Update qualitative cache with new data."""
        try:
            cache = {}
            if os.path.exists(self.qualitative_cache_file):
                with open(self.qualitative_cache_file, 'r') as f:
                    cache = json.load(f)
            
            cache[ticker] = {
                'auditor_notes': data.get('auditor_notes', {}),
                'rpt_notes': data.get('rpt_notes', {}),
            }
            
            with open(self.qualitative_cache_file, 'w') as f:
                json.dump(cache, f, indent=2)
                
        except Exception as e:
            print(f"[PDFFetcher] Cache update failed: {e}")
    
    def _get_unavailability_reason(self, ticker: str) -> str:
        """Get reason for unavailability."""
        if ticker not in self.SCRIP_CODES:
            return f"BSE scrip code not found for {ticker}. Manual PDF upload required."
        return f"Could not fetch annual report for {ticker} from BSE."
    
    def _get_recommendation(self, ticker: str) -> str:
        """Get recommendation for user."""
        return (
            f"To enable auditor sentiment analysis for {ticker}:\n"
            f"1. Download annual report PDF from BSE/NSE\n"
            f"2. Place in: {self.cache_dir}/{ticker}_YYYY_annual_report.pdf\n"
            f"3. Or add to demo_qualitative_cache.json manually"
        )
    
    def get_supported_tickers(self) -> List[str]:
        """Get list of tickers with known BSE scrip codes."""
        return list(self.SCRIP_CODES.keys())
    
    def add_scrip_code(self, ticker: str, scrip_code: str):
        """Add a new ticker to scrip code mapping."""
        self.SCRIP_CODES[ticker.upper()] = scrip_code


# Convenience function
def fetch_annual_report_notes(ticker: str) -> Dict[str, Any]:
    """
    Convenience function to fetch notes for a ticker.
    
    Example:
        notes = fetch_annual_report_notes("YESBANK")
        if notes['available']:
            print(notes['auditor_notes'])
    """
    fetcher = AnnualReportFetcher()
    return fetcher.fetch_notes(ticker)
