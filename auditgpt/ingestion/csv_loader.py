"""
CSV data loader for AuditGPT.

Loads pre-cached financial data from CSV files.
"""

import pandas as pd
from typing import Dict, Optional, Any, List
import os


class CSVLoader:
    """
    Loads financial data from cached CSV files.
    
    CSV naming convention:
    - {TICKER}_pnl.csv - Profit & Loss
    - {TICKER}_bs.csv - Balance Sheet  
    - {TICKER}_cf.csv - Cash Flow
    """
    
    def __init__(self, data_dir: str = "."):
        """
        Initialize the CSV loader.
        
        Args:
            data_dir: Directory containing CSV files
        """
        self.data_dir = data_dir
    
    def load_company_data(self, ticker: str) -> Optional[Dict[str, Any]]:
        """
        Load all available CSV data for a company.
        
        Args:
            ticker: Company ticker symbol
            
        Returns:
            Dict with DataFrames, or None if no data found
        """
        data = {'ticker': ticker}
        found_any = False
        
        # Try loading each type of statement
        pnl = self._load_csv(ticker, 'pnl')
        if pnl is not None:
            data['pnl'] = pnl
            found_any = True
        
        bs = self._load_csv(ticker, 'bs')
        if bs is not None:
            data['balance_sheet'] = bs
            found_any = True
        
        cf = self._load_csv(ticker, 'cf')
        if cf is not None:
            data['cash_flow'] = cf
            found_any = True
        
        if not found_any:
            return None
        
        # Set default sector (can be overridden)
        data['sector'] = self._infer_sector(ticker)
        data['name'] = ticker
        
        return data
    
    def _load_csv(self, ticker: str, suffix: str) -> Optional[pd.DataFrame]:
        """Load a single CSV file."""
        filename = f"{ticker}_{suffix}.csv"
        filepath = os.path.join(self.data_dir, filename)
        
        if not os.path.exists(filepath):
            return None
        
        try:
            df = pd.read_csv(filepath, index_col=0)
            df.index = df.index.astype(str)
            return df
        except Exception as e:
            print(f"Error loading {filepath}: {e}")
            return None
    
    def _infer_sector(self, ticker: str) -> str:
        """Infer sector from ticker name."""
        # Known bank tickers
        banks = ['HDFCBANK', 'ICICIBANK', 'KOTAKBANK', 'AXISBANK', 'SBIN', 
                 'PNB', 'BANKBARODA', 'YESBANK', 'CANBK', 'UNIONBANK']
        if ticker in banks:
            return 'BANK'
        
        # Known IT tickers
        it_companies = ['TCS', 'INFY', 'WIPRO', 'HCLTECH', 'TECHM', 'LTIM']
        if ticker in it_companies:
            return 'IT'
        
        return 'DEFAULT'
    
    def list_available_tickers(self) -> List[str]:
        """List all tickers with available CSV data."""
        tickers = set()
        
        for filename in os.listdir(self.data_dir):
            if filename.endswith('_pnl.csv'):
                ticker = filename.replace('_pnl.csv', '')
                tickers.add(ticker)
            elif filename.endswith('_bs.csv'):
                ticker = filename.replace('_bs.csv', '')
                tickers.add(ticker)
            elif filename.endswith('_cf.csv'):
                ticker = filename.replace('_cf.csv', '')
                tickers.add(ticker)
        
        return sorted(tickers)
    
    def has_data(self, ticker: str) -> bool:
        """Check if any CSV data exists for a ticker."""
        for suffix in ['pnl', 'bs', 'cf']:
            filepath = os.path.join(self.data_dir, f"{ticker}_{suffix}.csv")
            if os.path.exists(filepath):
                return True
        return False
