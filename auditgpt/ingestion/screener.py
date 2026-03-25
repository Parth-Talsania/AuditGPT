"""
Data acquisition from screener.in for AuditGPT.

Fetches and cleans 10-year financial data including:
- Profit & Loss statements
- Balance Sheets
- Cash Flow statements
- Financial ratios
"""

import pandas as pd
import numpy as np
import requests
from bs4 import BeautifulSoup
from typing import Dict, Optional, Any, List
import warnings

from auditgpt.config.constants import SECTOR_MAPPING

warnings.filterwarnings('ignore')


class DataAcquisition:
    """
    Handles fetching and cleaning financial data from screener.in.
    
    Provides 10-year historical financial data for NSE-listed companies.
    """
    
    def __init__(self, cache_enabled: bool = True):
        """
        Initialize the data acquisition module.
        
        Args:
            cache_enabled: Whether to cache fetched data in memory
        """
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        self.cache: Dict[str, Dict[str, Any]] = {}
        self.cache_enabled = cache_enabled
    
    def parse_table_to_df(self, table) -> Optional[pd.DataFrame]:
        """Parse HTML table to DataFrame."""
        rows = table.find_all('tr')
        if not rows:
            return None
        
        data = []
        for row in rows:
            cells = row.find_all(['th', 'td'])
            row_data = [cell.get_text(strip=True) for cell in cells]
            if row_data:
                data.append(row_data)
        
        if not data:
            return None
        
        df = pd.DataFrame(data[1:], columns=data[0])
        return df
    
    def clean_and_transpose(self, df: pd.DataFrame) -> Optional[pd.DataFrame]:
        """Clean and transpose financial DataFrame."""
        if df is None or df.empty:
            return None
        
        df = df.dropna(how='all').dropna(axis=1, how='all')
        
        if df.empty or df.shape[1] < 2:
            return None
        
        first_col = df.columns[0]
        df = df.set_index(first_col)
        df = df.T
        
        # Extract year from index
        df.index = df.index.astype(str).str.extract(r'(\d{4})')[0]
        df = df[df.index.notna()]
        
        # Clean numeric values
        df = df.replace({',': '', '%': ''}, regex=True)
        df = df.apply(pd.to_numeric, errors='coerce')
        
        # DON'T fill NaN with 0 - this causes issues with missing data
        # Instead, leave NaN to be handled by analysis code
        
        return df
    
    def fetch_company_data(self, ticker: str) -> Optional[Dict[str, Any]]:
        """
        Fetch complete financial data for a company.
        
        Args:
            ticker: NSE ticker symbol
            
        Returns:
            Dict containing all financial data, or None if fetch failed
        """
        # Check cache first
        if self.cache_enabled and ticker in self.cache:
            return self.cache[ticker]
        
        # Try consolidated first, then standalone
        base_url = f"https://www.screener.in/company/{ticker}/consolidated/"
        
        try:
            response = requests.get(base_url, headers=self.headers, timeout=30)
            
            if response.status_code != 200 or 'Page not found' in response.text:
                base_url = f"https://www.screener.in/company/{ticker}/"
                response = requests.get(base_url, headers=self.headers, timeout=30)
                if response.status_code != 200:
                    return None
            
            soup = BeautifulSoup(response.text, 'html5lib')
            data = {'ticker': ticker}
            
            # Extract company name
            name_tag = soup.find('h1')
            data['name'] = name_tag.get_text(strip=True) if name_tag else ticker
            
            # Extract sector from index membership
            data['sector'] = self._extract_sector(soup)
            data['indices'] = self._extract_indices(soup)
            
            # Extract financial tables
            section_mappings = [
                ('profit-loss', 'pnl'),
                ('balance-sheet', 'balance_sheet'),
                ('cash-flow', 'cash_flow'),
                ('ratios', 'ratios'),
            ]
            
            for section_id, key in section_mappings:
                section = soup.find('section', id=section_id)
                if section:
                    table = section.find('table')
                    if table:
                        df = self.parse_table_to_df(table)
                        if df is not None and not df.empty:
                            data[key] = self.clean_and_transpose(df)
            
            # Extract quarterly data
            quarters_section = soup.find('section', id='quarters')
            if quarters_section:
                table = quarters_section.find('table')
                if table:
                    df = self.parse_table_to_df(table)
                    if df is not None:
                        data['quarters'] = self.clean_and_transpose(df)
            
            # Cache the data
            if self.cache_enabled:
                self.cache[ticker] = data
            
            return data
            
        except Exception as e:
            print(f"Error fetching {ticker}: {e}")
            return None
    
    def fetch_all_data(self, ticker: str) -> Optional[Dict[str, Any]]:
        """
        Alias for fetch_company_data for backward compatibility.
        
        Args:
            ticker: NSE ticker symbol
            
        Returns:
            Dict containing all financial data, or None if fetch failed
        """
        return self.fetch_company_data(ticker)
    
    def _extract_sector(self, soup) -> str:
        """Extract sector from Nifty index membership."""
        for tag in soup.find_all(['span', 'div', 'a']):
            text = tag.get_text(strip=True)
            for index_name, sector in SECTOR_MAPPING.items():
                if index_name in text:
                    return sector
        return 'DEFAULT'
    
    def _extract_indices(self, soup) -> List[str]:
        """Extract all index memberships."""
        indices = []
        for tag in soup.find_all(['span', 'div', 'a']):
            text = tag.get_text(strip=True)
            if 'Nifty' in text and len(text) < 50:
                indices.append(text)
        return list(set(indices))
    
    def get_data_availability(self, data: Dict[str, Any]) -> Dict[str, bool]:
        """
        Check what data is available for a company.
        
        Returns dict indicating which data types are present.
        """
        return {
            'pnl': data.get('pnl') is not None,
            'balance_sheet': data.get('balance_sheet') is not None,
            'cash_flow': data.get('cash_flow') is not None,
            'ratios': data.get('ratios') is not None,
            'quarters': data.get('quarters') is not None,
            'auditor_notes': False,  # Would be True if PDF parsing done
        }
    
    def clear_cache(self):
        """Clear the data cache."""
        self.cache.clear()
    
    def preload_cache(self, tickers: List[str], verbose: bool = False) -> Dict[str, bool]:
        """
        Preload data for multiple tickers into cache.
        
        Args:
            tickers: List of tickers to preload
            verbose: Print progress
            
        Returns:
            Dict mapping tickers to success status
        """
        results = {}
        for ticker in tickers:
            if verbose:
                print(f"  Preloading {ticker}...")
            data = self.fetch_company_data(ticker)
            results[ticker] = data is not None
        return results


class RatioCalculator:
    """Calculates key financial ratios from statements."""
    
    @staticmethod
    def calculate_ratios(data: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate comprehensive financial ratios."""
        ratios = {}
        
        pnl = data.get('pnl')
        bs = data.get('balance_sheet')
        cf = data.get('cash_flow')
        sector = data.get('sector', 'DEFAULT')
        
        if pnl is None:
            return ratios
        
        years = pnl.index.tolist()
        
        # Revenue/Sales - prioritize based on sector
        if sector == 'BANK':
            revenue_col = next((c for c in pnl.columns if any(x in c for x in ['Interest', 'Revenue', 'Sales'])), None)
        else:
            revenue_col = next((c for c in pnl.columns if any(x in c for x in ['Sales', 'Revenue'])), None)
            if not revenue_col:
                revenue_col = next((c for c in pnl.columns if 'Interest' in c), None)
        
        if revenue_col:
            ratios['revenue'] = pnl[revenue_col].to_dict()
            ratios['revenue_growth'] = pnl[revenue_col].pct_change().to_dict()
            ratios['revenue_col'] = revenue_col
        
        # Net Profit
        if 'Net Profit' in pnl.columns:
            ratios['net_profit'] = pnl['Net Profit'].to_dict()
            ratios['profit_growth'] = pnl['Net Profit'].pct_change().to_dict()
        elif 'Net Profit+' in pnl.columns:
            ratios['net_profit'] = pnl['Net Profit+'].to_dict()
            ratios['profit_growth'] = pnl['Net Profit+'].pct_change().to_dict()
        
        # Operating Profit Margin
        if 'OPM %' in pnl.columns:
            ratios['opm'] = pnl['OPM %'].to_dict()
        elif 'Operating Profit' in pnl.columns and revenue_col:
            ratios['opm'] = (pnl['Operating Profit'] / pnl[revenue_col] * 100).to_dict()
        
        # Cash Flow ratios
        if cf is not None:
            cfo_col = next((c for c in cf.columns if 'Operating' in c), None)
            if cfo_col:
                ratios['cash_from_operations'] = cf[cfo_col].to_dict()
                
                # CFO to profit ratio
                if 'net_profit' in ratios:
                    np_series = pd.Series(ratios['net_profit'])
                    cfo_series = cf[cfo_col]
                    # Avoid division by zero
                    ratios['cfo_to_profit'] = (cfo_series / np_series.replace(0, np.nan)).to_dict()
        
        # Balance Sheet ratios
        if bs is not None:
            # Debt to Equity
            debt_col = None
            for col in ['Borrowings+', 'Borrowings', 'Total Debt']:
                if col in bs.columns:
                    debt_col = col
                    break
            
            equity_cols = [c for c in bs.columns if 'Equity' in c or 'Reserves' in c]
            
            if debt_col and equity_cols:
                total_equity = bs[equity_cols].sum(axis=1)
                ratios['debt_equity'] = (bs[debt_col] / total_equity.replace(0, np.nan)).to_dict()
                ratios['total_debt'] = bs[debt_col].to_dict()
            
            # Total Assets
            if 'Total Assets' in bs.columns:
                ratios['total_assets'] = bs['Total Assets'].to_dict()
        
        # Ratios from ratios table
        ratios_df = data.get('ratios')
        if ratios_df is not None:
            for col in ['ROCE %', 'ROE %', 'Debtor Days', 'Working Capital Days', 'Cash Conversion Cycle']:
                if col in ratios_df.columns:
                    key = col.lower().replace(' ', '_').replace('%', '')
                    ratios[key] = ratios_df[col].to_dict()
        
        return ratios
