"""
AuditGPT - Financial Statement Forensics Engine
"The AI That Reads 10 Years of Financial Statements and Finds What the Auditors Missed"

IAR Udaan Hackathon 2026 - Day 3 Problem Statement

Deliverables Checklist:
✅ Working prototype accepting any NSE-listed company name as live input
✅ Automated filing ingestion pipeline pulling real data
✅ Live demo: report generated in under 90 seconds
✅ Industry peer benchmarking showing at least 5 comparable companies
✅ Auditor note sentiment analysis showing language change over filing history
✅ Every red flag cited with exact filing year, statement type, and line reference
✅ Industry-specific anomaly contextualization (THE TWIST requirement)
"""

import pandas as pd
import numpy as np
import requests
from bs4 import BeautifulSoup
import warnings
from datetime import datetime
import json
import os
import re
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed

warnings.filterwarnings('ignore')

# ============================================
# CONFIGURATION & CONSTANTS
# ============================================

# Fraud precursor patterns based on historical cases (Satyam, Yes Bank, IL&FS, DHFL)
FRAUD_PATTERNS = {
    'revenue_cash_divergence': {
        'description': 'Revenue growing faster than operating cash flow',
        'threshold': 0.3,  # 30% divergence over 3 years
        'weight': 0.25
    },
    'debt_explosion': {
        'description': 'Debt growing faster than assets',
        'threshold': 0.5,  # 50% faster
        'weight': 0.20
    },
    'working_capital_deterioration': {
        'description': 'Working capital days increasing significantly',
        'threshold': 0.4,  # 40% increase
        'weight': 0.15
    },
    'profit_quality_decline': {
        'description': 'Net profit growing but cash from operations declining',
        'threshold': 0.25,
        'weight': 0.20
    },
    'roce_decline': {
        'description': 'Return on capital employed declining consistently',
        'threshold': -0.2,  # 20% decline
        'weight': 0.10
    },
    'debtor_days_spike': {
        'description': 'Debtor days increasing abnormally',
        'threshold': 0.3,  # 30% increase
        'weight': 0.10
    }
}

# Industry-specific thresholds
INDUSTRY_NORMS = {
    'IT': {
        'debt_equity_max': 0.5,
        'current_ratio_min': 1.5,
        'roce_min': 20,
        'debtor_days_max': 90,
        'opm_min': 15
    },
    'BANK': {
        'debt_equity_max': 15,
        'current_ratio_min': 0.8,
        'roce_min': 8,
        'npa_max': 5,
        'car_min': 12
    },
    'PHARMA': {
        'debt_equity_max': 1.0,
        'current_ratio_min': 1.2,
        'roce_min': 15,
        'rd_sales_min': 5,
        'opm_min': 12
    },
    'INFRA': {
        'debt_equity_max': 2.5,
        'current_ratio_min': 1.0,
        'roce_min': 10,
        'debtor_days_max': 120,
        'opm_min': 10
    },
    'REALTY': {
        'debt_equity_max': 2.0,
        'current_ratio_min': 1.0,
        'roce_min': 10,
        'debtor_days_max': 120,
        'opm_min': 15
    },
    'AUTO': {
        'debt_equity_max': 1.2,
        'current_ratio_min': 1.1,
        'roce_min': 14,
        'debtor_days_max': 60,
        'opm_min': 10
    },
    'METAL': {
        'debt_equity_max': 1.5,
        'current_ratio_min': 1.1,
        'roce_min': 12,
        'debtor_days_max': 75,
        'opm_min': 12
    },
    'ENERGY': {
        'debt_equity_max': 1.8,
        'current_ratio_min': 1.0,
        'roce_min': 10,
        'debtor_days_max': 90,
        'opm_min': 10
    },
    'FMCG': {
        'debt_equity_max': 0.8,
        'current_ratio_min': 1.1,
        'roce_min': 18,
        'debtor_days_max': 60,
        'opm_min': 12
    },
    'FINANCE': {
        'debt_equity_max': 8,
        'current_ratio_min': 1.0,
        'roce_min': 10,
        'debtor_days_max': 90,
        'opm_min': 10
    },
    'DEFAULT': {
        'debt_equity_max': 1.5,
        'current_ratio_min': 1.2,
        'roce_min': 12,
        'debtor_days_max': 90,
        'opm_min': 10
    }
}

SECTOR_MAPPING = {
    'Nifty IT': 'IT',
    'Nifty Bank': 'BANK',
    'Nifty Private Bank': 'BANK',
    'Nifty PSU Bank': 'BANK',
    'Nifty Pharma': 'PHARMA',
    'Nifty Healthcare': 'PHARMA',
    'Nifty Infra': 'INFRA',
    'Nifty Realty': 'REALTY',
    'Nifty Auto': 'AUTO',
    'Nifty Metal': 'METAL',
    'Nifty FMCG': 'FMCG',
    'Nifty Energy': 'ENERGY',
    'Nifty Financial Services': 'FINANCE',
}

SECTOR_KEYWORDS = {
    'BANK': ['bank', 'banking', 'lender', 'nbfc'],
    'FINANCE': ['financial services', 'payments', 'fintech', 'consumer finance', 'asset management', 'insurance'],
    'IT': ['software', 'information technology', 'it services', 'consulting'],
    'PHARMA': ['pharma', 'pharmaceutical', 'healthcare', 'formulations'],
    'REALTY': ['realty', 'real estate', 'property development'],
    'INFRA': ['infrastructure', 'construction', 'engineering', 'capital goods', 'projects'],
    'AUTO': ['automobile', 'auto', 'vehicle', 'tractor', 'motor'],
    'METAL': ['metal', 'steel', 'aluminium', 'mining', 'ore'],
    'ENERGY': ['energy', 'power', 'oil', 'gas', 'utility'],
    'FMCG': ['fmcg', 'consumer goods', 'foods', 'beverages', 'packaged food']
}

PEER_GROUPS = {
    'IT': ['TCS', 'INFY', 'HCLTECH', 'WIPRO', 'TECHM', 'LTIM'],
    'BANK': ['HDFCBANK', 'ICICIBANK', 'KOTAKBANK', 'AXISBANK', 'SBIN', 'PNB', 'BANKBARODA', 'YESBANK'],
    'PHARMA': ['SUNPHARMA', 'DRREDDY', 'CIPLA', 'DIVISLAB', 'LUPIN', 'AUROPHARMA'],
    'INFRA': ['LT', 'KEC', 'PNCINFRA', 'NBCC', 'IRB', 'KNRCON'],
    'REALTY': ['DLF', 'GODREJPROP', 'OBEROIRLTY', 'PRESTIGE', 'PHOENIXLTD', 'BRIGADE'],
    'AUTO': ['MARUTI', 'TATAMOTORS', 'M&M', 'BAJAJ-AUTO', 'HEROMOTOCO', 'EICHERMOT'],
    'METAL': ['TATASTEEL', 'HINDALCO', 'JSWSTEEL', 'JINDALSTEL', 'NMDC', 'SAIL', 'VEDL'],
    'ENERGY': ['RELIANCE', 'ONGC', 'IOC', 'BPCL', 'HINDPETRO', 'POWERGRID', 'NTPC'],
    'FMCG': ['HINDUNILVR', 'ITC', 'NESTLEIND', 'BRITANNIA', 'DABUR', 'TATACONSUM'],
    'FINANCE': ['BAJFINANCE', 'JIOFIN', 'CHOLAFIN', 'SHRIRAMFIN', 'SBICARD', 'LICHSGFIN'],
    'DEFAULT': ['RELIANCE', 'ITC', 'LT', 'TCS', 'ICICIBANK']
}


# ============================================
# DATA ACQUISITION MODULE
# ============================================

class DataAcquisition:
    """Handles fetching and cleaning financial data from screener.in"""
    
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        self.session = requests.Session()
        self.session.headers.update(self.headers)
        self.cache = {}

    def parse_table_to_df(self, table):
        """Parse HTML table to DataFrame"""
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
    
    def clean_and_transpose(self, df):
        """Clean and transpose financial DataFrame while preserving missing values."""
        if df is None or df.empty:
            return None

        df = df.dropna(how='all').dropna(axis=1, how='all')
        if df.empty or df.shape[1] < 2:
            return None

        first_col = df.columns[0]
        df = df.set_index(first_col).T
        df.index = df.index.astype(str).str.extract(r'(\d{4})')[0]
        df = df[df.index.notna()]
        df = df[~df.index.duplicated(keep='last')]

        df.columns = [str(c).strip() for c in df.columns]
        df = df.replace({'': np.nan, '-': np.nan, '--': np.nan, 'TTM': np.nan})
        df = df.replace({',': '', '%': '', '₹': ''}, regex=True)
        df = df.apply(pd.to_numeric, errors='coerce')

        return df

    def fetch_company_data(self, ticker):
        """Fetch complete financial data for a company"""
        if ticker in self.cache:
            return self.cache[ticker]
        
        base_url = f"https://www.screener.in/company/{ticker}/consolidated/"
        
        try:
            response = self.session.get(base_url, timeout=30)
            
            if response.status_code != 200 or 'Page not found' in response.text:
                base_url = f"https://www.screener.in/company/{ticker}/"
                response = self.session.get(base_url, timeout=30)
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
            for section_id, key in [('profit-loss', 'pnl'), ('balance-sheet', 'balance_sheet'), 
                                     ('cash-flow', 'cash_flow'), ('ratios', 'ratios')]:
                section = soup.find('section', id=section_id)
                if section:
                    table = section.find('table')
                    if table:
                        df = self.parse_table_to_df(table)
                        if df is not None and not df.empty:
                            data[key] = self.clean_and_transpose(df)
            
            # Extract quarterly data for recent trends
            quarters_section = soup.find('section', id='quarters')
            if quarters_section:
                table = quarters_section.find('table')
                if table:
                    df = self.parse_table_to_df(table)
                    if df is not None:
                        data['quarters'] = self.clean_and_transpose(df)
            
            self.cache[ticker] = data
            return data
            
        except Exception as e:
            print(f"Error fetching {ticker}: {e}")
            return None
    
    def _extract_sector(self, soup):
        """Extract sector from Nifty membership first, then page-text keywords."""
        for tag in soup.find_all(['span', 'div', 'a']):
            text = tag.get_text(strip=True)
            for index_name, sector in SECTOR_MAPPING.items():
                if index_name in text:
                    return sector

        page_text = ' '.join(soup.stripped_strings).lower()
        for sector, keywords in SECTOR_KEYWORDS.items():
            if any(keyword in page_text for keyword in keywords):
                return sector

        return 'DEFAULT'

    def _extract_indices(self, soup):
        """Extract all index memberships"""
        indices = []
        for tag in soup.find_all(['span', 'div', 'a']):
            text = tag.get_text(strip=True)
            if 'Nifty' in text and len(text) < 50:
                indices.append(text)
        return list(set(indices))


# ============================================
# AUDITOR SENTIMENT ANALYZER (NLP MODULE)
# ============================================

class AuditorSentimentAnalyzer:
    """
    Analyzes the language of auditor qualifications over time.
    Fulfills the deliverable: "Auditor note sentiment analysis showing 
    language change over the filing history"
    
    This module scans auditor notes for hedged/qualified language and
    tracks how the sentiment changes year over year.
    """
    
    # Red flag words indicating hedged/qualified audit opinions
    RED_FLAG_WORDS = [
        'subject to', 'uncertainty', 'material misstatement', 
        'emphasis of matter', 'except for', 'adverse', 'going concern',
        'discrepancy', 'fraud', 'restate', 'restated', 'restatement',
        'qualified opinion', 'disclaimer', 'limitation', 'unable to',
        'significant doubt', 'material weakness', 'deficiency',
        'non-compliance', 'deviation', 'irregularity', 'manipulation',
        'overstatement', 'understatement', 'contingent liability',
        'pending litigation', 'related party', 'suspicious'
    ]
    
    # Stable words indicating clean audit opinions
    STABLE_WORDS = [
        'true and fair view', 'unmodified', 'compliance', 
        'materially correct', 'fair presentation', 'unqualified',
        'clean opinion', 'properly maintained', 'adequate disclosure',
        'in accordance with', 'fairly represents', 'no material'
    ]
    
    # Sentiment change indicators (worsening language)
    ESCALATION_PATTERNS = [
        ('concern', 'significant concern'),
        ('uncertainty', 'material uncertainty'),
        ('observation', 'qualification'),
        ('emphasis', 'adverse')
    ]
    
    def __init__(self):
        self.sentiment_history = {}
    
    def analyze_sentiment_trend(self, notes_data_dict):
        """
        Calculates a hedged language score for each year.
        
        Args:
            notes_data_dict: Dict of {year: auditor_note_text}
            
        Returns:
            Dict with sentiment scores and detected keywords per year
        """
        sentiment_trend = {}
        
        for year, text in notes_data_dict.items():
            if not text:
                continue
                
            text_lower = str(text).lower()
            
            # Count red flag occurrences (weighted by severity)
            red_flags = 0
            hedged_keywords = []
            for word in self.RED_FLAG_WORDS:
                count = text_lower.count(word)
                if count > 0:
                    red_flags += count * (2 if word in ['fraud', 'adverse', 'disclaimer', 'going concern'] else 1)
                    hedged_keywords.append(word)
            
            # Count stable word occurrences
            stable = sum(text_lower.count(word) for word in self.STABLE_WORDS)
            
            # Sentiment score: Higher is more hedged/risky (negative = stable)
            score = (red_flags * 2) - stable
            
            # Determine sentiment category
            if score >= 10:
                category = 'CRITICAL'
            elif score >= 5:
                category = 'CONCERNING'
            elif score >= 0:
                category = 'NEUTRAL'
            else:
                category = 'STABLE'
            
            sentiment_trend[year] = {
                'score': score,
                'category': category,
                'red_flag_count': red_flags,
                'stable_count': stable,
                'hedged_keywords_found': hedged_keywords[:5],  # Top 5
                'text_length': len(text)
            }
        
        self.sentiment_history = sentiment_trend
        return sentiment_trend
    
    def detect_sentiment_deterioration(self, sentiment_trend):
        """
        Detects if auditor sentiment is deteriorating over time.
        
        Returns:
            List of anomaly dicts if deterioration detected
        """
        anomalies = []
        
        if not sentiment_trend or len(sentiment_trend) < 3:
            return anomalies
        
        years = sorted(sentiment_trend.keys())
        scores = [sentiment_trend[y]['score'] for y in years]
        
        # Check for consistent deterioration (3+ consecutive years of worsening)
        deterioration_streak = 0
        for i in range(1, len(scores)):
            if scores[i] > scores[i-1]:
                deterioration_streak += 1
            else:
                deterioration_streak = 0
            
            if deterioration_streak >= 2:
                anomalies.append({
                    'type': 'auditor_sentiment_deterioration',
                    'year': years[i],
                    'severity': 'HIGH' if deterioration_streak >= 3 else 'MEDIUM',
                    'description': f"Auditor language becoming more hedged for {deterioration_streak+1} consecutive years",
                    'pattern': 'Auditor qualifications increasing - potential hidden issues',
                    'statement_type': 'Auditor Report',
                    'source_reference': f"Auditor Notes FY{years[i-deterioration_streak]}-FY{years[i]}"
                })
        
        # Check for sudden spike in hedged language
        for i in range(1, len(years)):
            curr_score = sentiment_trend[years[i]]['score']
            prev_score = sentiment_trend[years[i-1]]['score']
            
            if curr_score > prev_score + 5:  # Significant jump
                anomalies.append({
                    'type': 'auditor_sentiment_spike',
                    'year': years[i],
                    'severity': 'HIGH',
                    'description': f"Auditor hedging score jumped from {prev_score} to {curr_score}",
                    'pattern': 'Sudden increase in qualified language - investigate cause',
                    'statement_type': 'Auditor Report',
                    'source_reference': f"Auditor Notes FY{years[i]}"
                })
        
        return anomalies
    
    def generate_sentiment_report(self, sentiment_trend):
        """
        Generate a formatted report of auditor sentiment over time.
        """
        if not sentiment_trend:
            return "No auditor notes data available for sentiment analysis."
        
        report_lines = []
        years = sorted(sentiment_trend.keys())
        
        for year in years:
            data = sentiment_trend[year]
            emoji = {'CRITICAL': '🔴', 'CONCERNING': '🟠', 'NEUTRAL': '🟡', 'STABLE': '🟢'}
            icon = emoji.get(data['category'], '⚪')
            
            report_lines.append(f"   {year}: {icon} [{data['category']}] Score: {data['score']}")
            if data['hedged_keywords_found']:
                report_lines.append(f"         Keywords: {', '.join(data['hedged_keywords_found'][:3])}")
        
        return "\n".join(report_lines)


# ============================================
# FINANCIAL RATIO CALCULATOR
# ============================================

class RatioCalculator:
    """Calculates key financial ratios from statements"""
    
    @staticmethod
    def calculate_ratios(data):
        """Calculate financial ratios with safer column selection and NaN handling."""
        ratios = {}

        pnl = data.get('pnl')
        bs = data.get('balance_sheet')
        cf = data.get('cash_flow')
        sector = data.get('sector', 'DEFAULT')

        if pnl is None or pnl.empty:
            return ratios

        def find_col(df, candidates=None, contains=None):
            if df is None or df.empty:
                return None
            cols = list(df.columns)
            if candidates:
                for candidate in candidates:
                    if candidate in cols:
                        return candidate
            if contains:
                contains = [contains] if isinstance(contains, str) else contains
                for col in cols:
                    lowered = str(col).lower()
                    if all(token.lower() in lowered for token in contains):
                        return col
            return None

        def series_to_dict(series):
            if series is None:
                return {}
            clean = series.dropna()
            return {str(idx): float(val) for idx, val in clean.items()}

        if sector == 'BANK':
            revenue_col = find_col(pnl, candidates=['Interest', 'Interest Earned', 'Revenue', 'Sales+'])
            if not revenue_col:
                revenue_col = next((c for c in pnl.columns if any(x in str(c) for x in ['Interest', 'Revenue', 'Sales'])), None)
        else:
            revenue_col = find_col(pnl, candidates=['Sales+', 'Sales', 'Revenue+', 'Revenue'])
            if not revenue_col:
                revenue_col = next((c for c in pnl.columns if any(x in str(c) for x in ['Sales', 'Revenue'])), None)

        if revenue_col:
            ratios['revenue'] = series_to_dict(pnl[revenue_col])
            ratios['revenue_growth'] = series_to_dict(pnl[revenue_col].pct_change())
            ratios['revenue_col'] = revenue_col

        net_profit_col = find_col(pnl, candidates=['Net Profit+', 'Net Profit'])
        if net_profit_col:
            ratios['net_profit'] = series_to_dict(pnl[net_profit_col])
            ratios['profit_growth'] = series_to_dict(pnl[net_profit_col].pct_change())

        opm_col = find_col(pnl, candidates=['OPM %'])
        if opm_col:
            ratios['opm'] = series_to_dict(pnl[opm_col])
        else:
            operating_profit_col = find_col(pnl, candidates=['Operating Profit+', 'Operating Profit'])
            if operating_profit_col and revenue_col:
                ratios['opm'] = series_to_dict((pnl[operating_profit_col] / pnl[revenue_col]) * 100)

        if cf is not None and not cf.empty:
            cfo_col = find_col(cf, candidates=['Cash from Operating Activity+', 'Cash from Operating Activity', 'Cash from Operations+', 'Cash from Operations'])
            if not cfo_col:
                cfo_col = next((c for c in cf.columns if 'operating' in str(c).lower()), None)
            if cfo_col:
                ratios['cash_from_operations'] = series_to_dict(cf[cfo_col])
                if net_profit_col:
                    profit_series = pnl[net_profit_col].replace(0, np.nan)
                    ratios['cfo_to_profit'] = series_to_dict(cf[cfo_col] / profit_series)

        if bs is not None and not bs.empty:
            debt_col = find_col(bs, candidates=['Borrowings+', 'Borrowings'])
            equity_cols = [c for c in bs.columns if any(token in str(c) for token in ['Equity', 'Reserves'])]
            if debt_col and equity_cols:
                total_equity = bs[equity_cols].sum(axis=1).replace(0, np.nan)
                ratios['debt_equity'] = series_to_dict(bs[debt_col] / total_equity)
                ratios['total_debt'] = series_to_dict(bs[debt_col])

            asset_col = find_col(bs, candidates=['Total Assets', 'Total Assets+'])
            if asset_col:
                ratios['total_assets'] = series_to_dict(bs[asset_col])

        ratios_df = data.get('ratios')
        if ratios_df is not None and not ratios_df.empty:
            for col in ['ROCE %', 'Debtor Days', 'Working Capital Days', 'Cash Conversion Cycle']:
                if col in ratios_df.columns:
                    ratios[col.lower().replace(' ', '_').replace('%', '')] = series_to_dict(ratios_df[col])

        return ratios



# ============================================
# ANOMALY DETECTION ENGINE
# ============================================

class AnomalyDetector:
    """Detects anomalies in financial data with structural break awareness"""
    
    def __init__(self, industry_norms):
        self.industry_norms = industry_norms
        self.structural_break_years = set()  # Years with mergers/acquisitions
    
    def _detect_structural_breaks(self, data, ratios):
        """
        Detect structural scale shifts (M&A, demergers, major business-model changes).
        Require confirmation from both revenue and asset jumps where possible.
        """
        revenue_jump_years = set()
        asset_jump_years = set()

        revenue = ratios.get('revenue', {})
        if revenue:
            years = sorted(revenue.keys())
            for i in range(1, len(years)):
                curr = revenue.get(years[i], np.nan)
                prev = revenue.get(years[i-1], np.nan)
                if pd.notna(prev) and prev > 0 and pd.notna(curr) and curr > prev * 1.5:
                    revenue_jump_years.add(years[i])

        bs = data.get('balance_sheet')
        if bs is not None and not bs.empty:
            asset_col = next((c for c in bs.columns if 'Total Assets' in str(c)), None)
            if asset_col is None:
                asset_candidates = [c for c in bs.columns if 'Assets' in str(c)]
                asset_col = asset_candidates[0] if asset_candidates else None
            if asset_col is not None:
                total_assets = bs[asset_col].dropna().to_dict()
                years = sorted(total_assets.keys())
                for i in range(1, len(years)):
                    curr = total_assets.get(years[i], np.nan)
                    prev = total_assets.get(years[i-1], np.nan)
                    if pd.notna(prev) and prev > 0 and pd.notna(curr) and curr > prev * 1.5:
                        asset_jump_years.add(years[i])

        confirmed = revenue_jump_years & asset_jump_years
        extreme_single_side = set()
        for year_set, data_dict in [(revenue_jump_years, revenue), (asset_jump_years, ratios.get('total_assets', {}))]:
            for year in year_set:
                years = sorted(data_dict.keys()) if data_dict else []
                if year in years:
                    idx = years.index(year)
                    if idx > 0:
                        prev = data_dict.get(years[idx-1], np.nan)
                        curr = data_dict.get(year, np.nan)
                        if pd.notna(prev) and prev > 0 and pd.notna(curr) and curr > prev * 2.0:
                            extreme_single_side.add(year)

        structural_years = confirmed | extreme_single_side
        expanded = set(structural_years)
        for year in structural_years:
            try:
                next_year = str(int(year) + 1)
                expanded.add(next_year)
            except Exception:
                pass

        self.structural_break_years = expanded
        return expanded

    def detect_anomalies(self, data, ratios, sector='DEFAULT'):
        """Detect all anomalies in financial data"""
        anomalies = []
        norms = self.industry_norms.get(sector, self.industry_norms['DEFAULT'])
        
        # First, detect structural breaks (mergers/acquisitions)
        structural_years = self._detect_structural_breaks(data, ratios)
        
        # Add informational note about structural breaks
        for year in structural_years:
            anomalies.append({
                'type': 'structural_break',
                'year': year,
                'severity': 'INFO',  # Not a risk, just information
                'description': f"Structural scale shift detected (>50% revenue/assets growth) - investigate merger, acquisition, or business-model change",
                'pattern': 'Structural shift detected - suppressing noisy growth-based alerts'
            })
        
        # 1. Revenue-Cash Flow Divergence (SKIP FOR BANKS - loans are cash outflows)
        if sector != 'BANK':
            anomalies.extend(self._check_revenue_cash_divergence(ratios))
        
        # 2. Debt Explosion (adjusted for sector)
        anomalies.extend(self._check_debt_growth(ratios, norms, sector))
        
        # 3. Profit Quality Decline (SKIP FOR BANKS - different cash flow dynamics)
        if sector != 'BANK':
            anomalies.extend(self._check_profit_quality(ratios))
        
        # 4. Working Capital Deterioration (SKIP FOR BANKS - not applicable)
        if sector != 'BANK':
            anomalies.extend(self._check_working_capital(ratios, norms))
        
        # 5. ROCE Decline
        anomalies.extend(self._check_roce_decline(ratios, norms))
        
        # 6. Debtor Days Spike (SKIP FOR BANKS - not applicable)
        if sector != 'BANK':
            anomalies.extend(self._check_debtor_days(ratios, norms))
        
        # 7. Historical Trend Breaks
        anomalies.extend(self._check_trend_breaks(ratios))
        
        # 8. BANK-SPECIFIC CHECKS
        if sector == 'BANK':
            anomalies.extend(self._check_bank_specific(ratios, norms, data))
        
        # 9. Related Party Transaction Check (if data available)
        anomalies.extend(self._check_related_party(data, ratios))
        
        return anomalies
    
    def _check_revenue_cash_divergence(self, ratios):
        """Check if revenue growth is unsupported by operating cash flow, without fake -100% math."""
        anomalies = []

        cfo = ratios.get('cash_from_operations', {})
        revenue = ratios.get('revenue', {})
        if not cfo or not revenue:
            return anomalies

        years = sorted(set(revenue.keys()) & set(cfo.keys()))
        if len(years) < 3:
            return anomalies

        for i in range(2, len(years)):
            start_year = years[i - 2]
            end_year = years[i]
            if end_year in self.structural_break_years:
                continue

            rev_start = revenue.get(start_year, np.nan)
            rev_end = revenue.get(end_year, np.nan)
            if pd.isna(rev_start) or pd.isna(rev_end) or rev_start <= 0:
                continue

            rev_growth = (rev_end - rev_start) / rev_start
            if rev_growth <= 0.20:
                continue

            cfo_start = cfo.get(start_year, np.nan)
            cfo_end = cfo.get(end_year, np.nan)
            cfo_window = np.array([cfo.get(y, np.nan) for y in years[i - 2:i + 1]], dtype=float)
            rev_window = np.array([revenue.get(y, np.nan) for y in years[i - 2:i + 1]], dtype=float)
            cumulative_cfo = float(np.nansum(cfo_window))
            cumulative_revenue = float(np.nansum(rev_window))
            cfo_margin = (cumulative_cfo / cumulative_revenue) if cumulative_revenue > 0 else np.nan

            if pd.notna(cfo_start) and pd.notna(cfo_end) and cfo_start > 0 and cfo_end > 0:
                cfo_growth = (cfo_end - cfo_start) / cfo_start
                if cfo_growth < rev_growth - 0.35:
                    anomalies.append({
                        'type': 'revenue_cash_divergence',
                        'year': end_year,
                        'severity': 'HIGH' if rev_growth - cfo_growth > 0.70 else 'MEDIUM',
                        'description': f"Revenue grew {rev_growth * 100:.1f}% but CFO grew only {cfo_growth * 100:.1f}% over 3 years",
                        'pattern': FRAUD_PATTERNS['revenue_cash_divergence']['description'],
                        'statement_type': 'P&L + Cash Flow Statement',
                        'source_reference': f"P&L > Revenue > FY{start_year}-FY{end_year} vs Cash Flow > CFO > FY{start_year}-FY{end_year}"
                    })
            else:
                if cumulative_cfo <= 0 and rev_growth > 0.25:
                    anomalies.append({
                        'type': 'revenue_cash_divergence',
                        'year': end_year,
                        'severity': 'HIGH',
                        'description': f"Revenue grew {rev_growth * 100:.1f}% over 3 years but cumulative CFO stayed negative",
                        'pattern': 'Revenue growth not supported by cash generation',
                        'statement_type': 'P&L + Cash Flow Statement',
                        'source_reference': f"P&L > Revenue > FY{start_year}-FY{end_year} vs Cash Flow > CFO > FY{start_year}-FY{end_year}"
                    })
                elif pd.notna(cfo_margin) and cfo_margin < 0.05 and rev_growth > 0.25:
                    anomalies.append({
                        'type': 'revenue_cash_divergence',
                        'year': end_year,
                        'severity': 'MEDIUM',
                        'description': f"Revenue grew {rev_growth * 100:.1f}% over 3 years but cumulative CFO margin was only {cfo_margin * 100:.1f}%",
                        'pattern': 'Weak cash conversion despite top-line growth',
                        'statement_type': 'P&L + Cash Flow Statement',
                        'source_reference': f"P&L > Revenue > FY{start_year}-FY{end_year} vs Cash Flow > CFO > FY{start_year}-FY{end_year}"
                    })

        return anomalies

    def _check_debt_growth(self, ratios, norms, sector='DEFAULT'):
        """Check for explosive debt growth with materiality thresholds"""
        anomalies = []
        
        # Skip debt checks for banks - they're supposed to have high debt
        if sector == 'BANK':
            return anomalies
        
        debt = ratios.get('total_debt', {})
        debt_equity = ratios.get('debt_equity', {})
        revenue = ratios.get('revenue', {})
        
        if debt and revenue:
            years = sorted(debt.keys())
            for i in range(1, len(years)):
                year = years[i]
                
                # Skip structural break years
                if year in self.structural_break_years:
                    continue
                
                curr_debt = debt.get(year, 0)
                prev_debt = debt.get(years[i-1], 0)
                curr_revenue = revenue.get(year, 1)
                
                # MATERIALITY CHECK: Only flag if debt is significant relative to revenue
                # AND the absolute increase is meaningful (>100 Cr or >5% of revenue)
                debt_to_revenue = curr_debt / curr_revenue if curr_revenue > 0 else 0
                debt_increase = curr_debt - prev_debt
                
                # Skip if previous debt was tiny (likely accounting changes like IFRS 16)
                if prev_debt > 0 and prev_debt < curr_revenue * 0.01:
                    continue  # Previous debt was immaterial (<1% of revenue)
                
                if prev_debt > 0 and curr_debt > prev_debt * 1.5:
                    # Only flag if debt is material (>5% of revenue) and increase is significant
                    if debt_to_revenue > 0.05 and debt_increase > curr_revenue * 0.03:
                        anomalies.append({
                            'type': 'debt_explosion',
                            'year': year,
                            'severity': 'HIGH' if curr_debt > prev_debt * 2 else 'MEDIUM',
                            'description': f"Debt increased by {((curr_debt/prev_debt)-1)*100:.1f}% (now {debt_to_revenue*100:.1f}% of revenue)",
                            'pattern': FRAUD_PATTERNS['debt_explosion']['description'],
                            'statement_type': 'Balance Sheet',
                            'source_reference': f"Balance Sheet > Borrowings > FY{year}"
                        })
        
        # Check debt/equity ratio against industry norm (skip structural break years)
        if debt_equity:
            max_de = norms.get('debt_equity_max', 1.5)
            for year, de in debt_equity.items():
                if year in self.structural_break_years:
                    continue
                if de > max_de * 1.5:
                    anomalies.append({
                        'type': 'high_leverage',
                        'year': year,
                        'severity': 'HIGH' if de > max_de * 2 else 'MEDIUM',
                        'description': f"Debt/Equity ratio {de:.2f} exceeds industry norm of {max_de}",
                        'pattern': 'Excessive leverage for industry',
                        'statement_type': 'Balance Sheet',
                        'source_reference': f"Balance Sheet > Debt/Equity Calculation > FY{year}"
                    })
        
        return anomalies
    
    def _check_profit_quality(self, ratios):
        """Check if profits are backed by cash"""
        anomalies = []
        
        cfo_to_profit = ratios.get('cfo_to_profit', {})
        profit = ratios.get('net_profit', {})
        cfo = ratios.get('cash_from_operations', {})
        
        if cfo_to_profit:
            for year, ratio in cfo_to_profit.items():
                if ratio < 0.5 and profit.get(year, 0) > 0:
                    anomalies.append({
                        'type': 'profit_quality_decline',
                        'year': year,
                        'severity': 'HIGH' if ratio < 0.3 else 'MEDIUM',
                        'description': f"CFO is only {ratio*100:.1f}% of Net Profit - poor earnings quality",
                        'pattern': FRAUD_PATTERNS['profit_quality_decline']['description'],
                        'statement_type': 'P&L + Cash Flow Statement',
                        'source_reference': f"P&L > Net Profit vs Cash Flow > CFO > FY{year}"
                    })
        
        # Check for consistent divergence
        if profit and cfo:
            years = sorted(set(profit.keys()) & set(cfo.keys()))
            divergence_count = 0
            for year in years[-5:]:  # Last 5 years
                p = profit.get(year, 0)
                c = cfo.get(year, 0)
                if p > 0 and c < p * 0.7:
                    divergence_count += 1
            
            if divergence_count >= 3:
                anomalies.append({
                    'type': 'persistent_profit_quality_issue',
                    'year': years[-1],
                    'severity': 'CRITICAL',
                    'description': f"Profit quality concerns in {divergence_count} of last 5 years",
                    'pattern': 'Persistent gap between reported profits and cash generation',
                    'statement_type': 'P&L + Cash Flow Statement',
                    'source_reference': f"P&L vs Cash Flow > Last 5 Years Analysis"
                })
        
        return anomalies
    
    def _check_working_capital(self, ratios, norms):
        """Check working capital deterioration"""
        anomalies = []
        
        wc_days = ratios.get('working_capital_days', {})
        
        if wc_days:
            years = sorted(wc_days.keys())
            if len(years) >= 3:
                # Check trend
                first_val = wc_days.get(years[0], 0)
                last_val = wc_days.get(years[-1], 0)
                
                if first_val > 0 and last_val > first_val * 1.4:
                    anomalies.append({
                        'type': 'working_capital_deterioration',
                        'year': years[-1],
                        'severity': 'MEDIUM',
                        'description': f"Working capital days increased from {first_val:.0f} to {last_val:.0f}",
                        'pattern': FRAUD_PATTERNS['working_capital_deterioration']['description'],
                        'statement_type': 'Financial Ratios',
                        'source_reference': f"Ratios > Working Capital Days > FY{years[0]}-FY{years[-1]}"
                    })
        
        return anomalies
    
    def _check_roce_decline(self, ratios, norms):
        """Check for consistent ROCE decline"""
        anomalies = []
        
        roce = ratios.get('roce_', {})
        min_roce = norms.get('roce_min', 12)
        
        if roce:
            years = sorted(roce.keys())
            if len(years) >= 3:
                # Check for consistent decline
                declining_years = 0
                for i in range(1, len(years)):
                    if roce.get(years[i], 0) < roce.get(years[i-1], 0):
                        declining_years += 1
                
                if declining_years >= len(years) - 2:  # Most years declining
                    anomalies.append({
                        'type': 'roce_decline',
                        'year': years[-1],
                        'severity': 'MEDIUM',
                        'description': f"ROCE has declined in {declining_years} of {len(years)-1} years",
                        'pattern': FRAUD_PATTERNS['roce_decline']['description'],
                        'statement_type': 'Financial Ratios',
                        'source_reference': f"Ratios > ROCE % > FY{years[0]}-FY{years[-1]}"
                    })
                
                # Check against industry norm
                last_roce = roce.get(years[-1], 0)
                if last_roce < min_roce:
                    anomalies.append({
                        'type': 'low_roce',
                        'year': years[-1],
                        'severity': 'LOW',
                        'description': f"ROCE {last_roce:.1f}% below industry minimum of {min_roce}%",
                        'pattern': 'Below industry average return on capital',
                        'statement_type': 'Financial Ratios',
                        'source_reference': f"Ratios > ROCE % > FY{years[-1]}"
                    })
        
        return anomalies
    
    def _check_debtor_days(self, ratios, norms):
        """Check for debtor days spike"""
        anomalies = []
        
        debtor_days = ratios.get('debtor_days', {})
        max_days = norms.get('debtor_days_max', 90)
        
        if debtor_days:
            years = sorted(debtor_days.keys())
            
            for i in range(1, len(years)):
                curr = debtor_days.get(years[i], 0)
                prev = debtor_days.get(years[i-1], 0)
                
                if prev > 0 and curr > prev * 1.3:
                    anomalies.append({
                        'type': 'debtor_days_spike',
                        'year': years[i],
                        'severity': 'MEDIUM',
                        'description': f"Debtor days spiked from {prev:.0f} to {curr:.0f}",
                        'pattern': FRAUD_PATTERNS['debtor_days_spike']['description'],
                        'statement_type': 'Financial Ratios',
                        'source_reference': f"Ratios > Debtor Days > FY{years[i]}"
                    })
                
                if curr > max_days:
                    anomalies.append({
                        'type': 'high_debtor_days',
                        'year': years[i],
                        'severity': 'LOW',
                        'description': f"Debtor days {curr:.0f} exceeds industry norm of {max_days}",
                        'pattern': 'Slower collections than industry average',
                        'statement_type': 'Financial Ratios',
                        'source_reference': f"Ratios > Debtor Days > FY{years[i]}"
                    })
        
        return anomalies
    
    def _check_trend_breaks(self, ratios):
        """Detect sudden breaks in historical trends - only flag significant ones"""
        anomalies = []
        
        # Only check key metrics that matter for fraud detection
        key_metrics = ['cfo_to_profit', 'debt_equity', 'opm']
        metric_statement_map = {
            'cfo_to_profit': 'P&L + Cash Flow Statement',
            'debt_equity': 'Balance Sheet',
            'opm': 'Profit & Loss Statement'
        }
        
        for metric_name in key_metrics:
            metric_data = ratios.get(metric_name, {})
            if not isinstance(metric_data, dict) or len(metric_data) < 5:
                continue
            
            years = sorted(metric_data.keys())
            values = [metric_data[y] for y in years]
            
            # Calculate rolling mean and std
            if len(values) >= 5:
                for i in range(4, len(values)):
                    historical = values[i-4:i]
                    current = values[i]
                    
                    mean = np.mean(historical)
                    std = np.std(historical)
                    
                    # Only flag if standard deviation is meaningful and deviation is extreme
                    if std > 0.1 and abs(current - mean) > 3 * std:
                        anomalies.append({
                            'type': 'trend_break',
                            'year': years[i],
                            'severity': 'LOW',
                            'description': f"{metric_name}: Value {current:.1f} deviates significantly from historical pattern (mean: {mean:.1f})",
                            'pattern': 'Statistical anomaly in historical trend',
                            'statement_type': metric_statement_map.get(metric_name, 'Financial Data'),
                            'source_reference': f"{metric_statement_map.get(metric_name, 'Data')} > {metric_name} > FY{years[i]}"
                        })
        
        return anomalies
    
    def _check_bank_specific(self, ratios, norms, data):
        """
        Bank-specific anomaly detection.
        For banks, focus on:
        - NPA (Non-Performing Assets) trends - GNPA and NNPA
        - Provisioning coverage
        - Net Interest Margin decline
        - Advances growth vs deposit growth
        - Capital Adequacy Ratio (CAR)
        """
        anomalies = []
        
        pnl = data.get('pnl')
        if pnl is None:
            return anomalies
        
        # Check Net Profit trend (sudden drops are red flags for banks)
        if 'Net Profit' in pnl.columns or 'Net Profit+' in pnl.columns:
            np_col = 'Net Profit+' if 'Net Profit+' in pnl.columns else 'Net Profit'
            net_profit = pnl[np_col].to_dict()
            years = sorted(net_profit.keys())
            
            # Check for sudden profit drops (>50% YoY decline)
            for i in range(1, len(years)):
                curr = net_profit.get(years[i], 0)
                prev = net_profit.get(years[i-1], 0)
                
                if prev > 0 and curr < prev * 0.5:
                    anomalies.append({
                        'type': 'bank_profit_collapse',
                        'year': years[i],
                        'severity': 'CRITICAL' if curr < 0 else 'HIGH',
                        'description': f"Net profit dropped {((prev-curr)/prev)*100:.1f}% from \u20b9{prev:,.0f} Cr to \u20b9{curr:,.0f} Cr",
                        'pattern': 'Sudden profit collapse - potential asset quality issues or provisioning spike',
                        'statement_type': 'Profit & Loss Statement',
                        'source_reference': f"P&L > {np_col} > FY{years[i]}"
                    })
                
                # Check for losses (red flag for banks)
                if curr < 0 and prev > 0:
                    anomalies.append({
                        'type': 'bank_loss',
                        'year': years[i],
                        'severity': 'CRITICAL',
                        'description': f"Bank reported loss of \u20b9{abs(curr):,.0f} Cr after profit of \u20b9{prev:,.0f} Cr",
                        'pattern': 'Bank turned loss-making - serious asset quality or provisioning issues',
                        'statement_type': 'Profit & Loss Statement',
                        'source_reference': f"P&L > {np_col} > FY{years[i]}"
                    })
        
        # Check Operating Profit Margin trend for banks
        if 'OPM %' in pnl.columns:
            opm = pnl['OPM %'].to_dict()
            years = sorted(opm.keys())
            
            if len(years) >= 3:
                recent_opm = [opm.get(y, 0) for y in years[-3:]]
                historical_opm = [opm.get(y, 0) for y in years[:-3]] if len(years) > 3 else recent_opm
                
                if historical_opm and np.mean(historical_opm) > 0:
                    if np.mean(recent_opm) < np.mean(historical_opm) * 0.7:
                        anomalies.append({
                            'type': 'bank_margin_compression',
                            'year': years[-1],
                            'severity': 'MEDIUM',
                            'description': f"Operating margin compressed from {np.mean(historical_opm):.1f}% to {np.mean(recent_opm):.1f}%",
                            'pattern': 'Declining margins may indicate rising funding costs or competitive pressure',
                            'statement_type': 'Profit & Loss Statement',
                            'source_reference': f"P&L > OPM % > FY{years[-3]}-FY{years[-1]}"
                        })
        
        # === NEW: Gross NPA (Asset Quality) Check ===
        ratios_df = data.get('ratios')
        if ratios_df is not None:
            # Look for NPA columns (handling different naming conventions)
            npa_col = next((c for c in ratios_df.columns if any(x in c for x in ['Gross NPA', 'GNPA', 'Gross Non'])), None)
            nnpa_col = next((c for c in ratios_df.columns if any(x in c for x in ['Net NPA', 'NNPA', 'Net Non'])), None)
            
            if npa_col:
                gnpa = ratios_df[npa_col].to_dict()
                years = sorted(gnpa.keys())
                max_npa = norms.get('npa_max', 5.0)
                
                for i in range(1, len(years)):
                    curr = gnpa.get(years[i], 0)
                    prev = gnpa.get(years[i-1], 0)
                    
                    # Flag 1: Sudden Spike in bad loans (>50% YoY increase)
                    if prev > 0 and curr > prev * 1.5:
                        anomalies.append({
                            'type': 'npa_spike',
                            'year': years[i],
                            'severity': 'CRITICAL',
                            'description': f"Gross NPA spiked by {((curr/prev)-1)*100:.1f}% to {curr:.2f}%",
                            'pattern': 'Rapid deterioration of asset quality - potential hidden bad loans',
                            'statement_type': 'Financial Ratios',
                            'source_reference': f"Ratios > {npa_col} > FY{years[i]}"
                        })
                    
                    # Flag 2: Consistently above industry norm (>1.5x norm)
                    elif curr > max_npa * 1.5:
                        anomalies.append({
                            'type': 'high_npa_baseline',
                            'year': years[i],
                            'severity': 'HIGH',
                            'description': f"Gross NPA at {curr:.2f}% is severely above industry norm ({max_npa}%)",
                            'pattern': 'Sustained toxic asset burden - requires provisioning scrutiny',
                            'statement_type': 'Financial Ratios',
                            'source_reference': f"Ratios > {npa_col} > FY{years[i]}"
                        })
                    
                    # Flag 3: Elevated NPA (>norm but <1.5x norm)
                    elif curr > max_npa:
                        anomalies.append({
                            'type': 'elevated_npa',
                            'year': years[i],
                            'severity': 'MEDIUM',
                            'description': f"Gross NPA at {curr:.2f}% exceeds industry norm of {max_npa}%",
                            'pattern': 'Asset quality stress - monitor provisioning adequacy',
                            'statement_type': 'Financial Ratios',
                            'source_reference': f"Ratios > {npa_col} > FY{years[i]}"
                        })
            
            # Check Net NPA trend as well
            if nnpa_col:
                nnpa = ratios_df[nnpa_col].to_dict()
                years = sorted(nnpa.keys())
                
                for i in range(1, len(years)):
                    curr = nnpa.get(years[i], 0)
                    prev = nnpa.get(years[i-1], 0)
                    
                    if prev > 0 and curr > prev * 1.5 and curr > 3:  # >50% spike AND >3%
                        anomalies.append({
                            'type': 'nnpa_spike',
                            'year': years[i],
                            'severity': 'CRITICAL',
                            'description': f"Net NPA spiked to {curr:.2f}% - provisioning may be inadequate",
                            'pattern': 'Net NPA spike indicates insufficient provision coverage',
                            'statement_type': 'Financial Ratios',
                            'source_reference': f"Ratios > {nnpa_col} > FY{years[i]}"
                        })
            
            # Check Capital Adequacy Ratio (CAR) if available
            car_col = next((c for c in ratios_df.columns if any(x in c for x in ['Capital Adequacy', 'CAR', 'CRAR'])), None)
            if car_col:
                car = ratios_df[car_col].to_dict()
                min_car = norms.get('car_min', 12)
                years = sorted(car.keys())
                
                for year in years:
                    curr_car = car.get(year, 0)
                    if curr_car > 0 and curr_car < min_car:
                        anomalies.append({
                            'type': 'low_capital_adequacy',
                            'year': year,
                            'severity': 'CRITICAL' if curr_car < 9 else 'HIGH',
                            'description': f"Capital Adequacy Ratio at {curr_car:.1f}% below regulatory minimum ({min_car}%)",
                            'pattern': 'Insufficient capital buffer - bank may need capital infusion',
                            'statement_type': 'Financial Ratios',
                            'source_reference': f"Ratios > {car_col} > FY{year}"
                        })
        
        return anomalies
    
    def _check_related_party(self, data, ratios):
        """
        Check for related-party-like anomalies using a very conservative proxy.
        Skip BANK/FINANCE where Other Income is a normal operating line item.
        """
        anomalies = []
        rpt_growth_data = {}

        sector = data.get('sector', 'DEFAULT')
        if sector in {'BANK', 'FINANCE'}:
            self.rpt_growth_data = rpt_growth_data
            return anomalies

        pnl = data.get('pnl')
        if pnl is None or pnl.empty:
            self.rpt_growth_data = rpt_growth_data
            return anomalies

        other_income_col = next((c for c in pnl.columns if 'Other Income' in str(c)), None)
        revenue_col = ratios.get('revenue_col')
        if not other_income_col or not revenue_col or revenue_col not in pnl.columns:
            self.rpt_growth_data = rpt_growth_data
            return anomalies

        other_income = pnl[other_income_col].to_dict()
        revenue = pnl[revenue_col].to_dict()
        years = sorted(set(other_income.keys()) & set(revenue.keys()))

        for year in years:
            oi = other_income.get(year, np.nan)
            rev = revenue.get(year, np.nan)
            rpt_growth_data[year] = {
                'other_income': float(0 if pd.isna(oi) else oi),
                'revenue': float(0 if pd.isna(rev) else rev),
                'oi_to_revenue_pct': float((oi / rev * 100) if pd.notna(oi) and pd.notna(rev) and rev > 0 else 0)
            }

        if len(years) >= 3:
            for i in range(2, len(years)):
                year = years[i]
                if year in self.structural_break_years:
                    continue

                oi_start = other_income.get(years[i - 2], np.nan)
                oi_end = other_income.get(year, np.nan)
                rev_start = revenue.get(years[i - 2], np.nan)
                rev_end = revenue.get(year, np.nan)
                if any(pd.isna(v) for v in [oi_start, oi_end, rev_start, rev_end]) or oi_start <= 0 or rev_start <= 0 or rev_end <= 0:
                    continue

                oi_pct = ((oi_end - oi_start) / oi_start) * 100
                rev_pct = ((rev_end - rev_start) / rev_start) * 100
                oi_rev_ratio = oi_end / rev_end * 100

                if oi_pct > rev_pct + 150 and oi_pct > 75 and oi_rev_ratio > 12:
                    anomalies.append({
                        'type': 'unusual_other_income',
                        'year': year,
                        'severity': 'MEDIUM',
                        'description': f"Other Income grew {oi_pct:.0f}% vs Revenue {rev_pct:.0f}% - now {oi_rev_ratio:.1f}% of revenue",
                        'pattern': 'Unusual Other Income growth may indicate one-time gains or related-party-style inflows',
                        'statement_type': 'Profit & Loss Statement',
                        'source_reference': f"P&L > {other_income_col} > FY{years[i-2]}-FY{year}"
                    })

        self.rpt_growth_data = rpt_growth_data
        return anomalies

    def get_rpt_growth_chart_data(self):
        """Returns RPT growth data for chart generation in reports."""
        return getattr(self, 'rpt_growth_data', {})


# ============================================
# PEER BENCHMARKING ENGINE
# ============================================

class PeerBenchmark:
    """Benchmarks company against industry peers"""
    
    def __init__(self, data_acquisition):
        self.data_acq = data_acquisition
        self.peer_data_cache = {}
    
    def get_peer_companies(self, sector, exclude_ticker=None):
        """Get list of peer companies for a sector"""
        peers = PEER_GROUPS.get(sector, [])
        if exclude_ticker:
            peers = [p for p in peers if p != exclude_ticker]
        return peers[:5]  # Return top 5 peers
    
    def fetch_peer_data(self, peers):
        """Fetch data for all peer companies concurrently for demo speed."""
        peer_data = {}
        pending = [peer for peer in peers if peer not in self.peer_data_cache]

        for peer in peers:
            if peer in self.peer_data_cache:
                peer_data[peer] = self.peer_data_cache[peer]

        if pending:
            with ThreadPoolExecutor(max_workers=min(5, len(pending))) as executor:
                future_map = {executor.submit(self.data_acq.fetch_company_data, peer): peer for peer in pending}
                for future in as_completed(future_map):
                    peer = future_map[future]
                    try:
                        data = future.result()
                    except Exception:
                        data = None
                    if data:
                        peer_data[peer] = data
                        self.peer_data_cache[peer] = data

        return peer_data

    def benchmark(self, company_data, company_ratios, sector):
        """Compare company metrics against peers using a robust peer median."""
        peers = self.get_peer_companies(sector, company_data.get('ticker'))
        peer_data = self.fetch_peer_data(peers)

        if not peer_data:
            return {'peers': [], 'comparisons': []}

        peer_ratios = {ticker: RatioCalculator.calculate_ratios(data) for ticker, data in peer_data.items()}
        comparisons = []
        metrics_to_compare = [
            ('revenue_growth', 'Revenue Growth', True),
            ('profit_growth', 'Profit Growth', True),
            ('opm', 'Operating Margin', True),
            ('roce_', 'ROCE', True),
            ('debt_equity', 'Debt/Equity', False),
            ('debtor_days', 'Debtor Days', False),
        ]

        for metric_key, metric_name, higher_better in metrics_to_compare:
            company_vals = company_ratios.get(metric_key, {})
            if not company_vals:
                continue

            candidate_years = sorted(company_vals.keys(), reverse=True)
            chosen = None
            for latest_year in candidate_years:
                company_val = company_vals.get(latest_year, np.nan)
                if pd.isna(company_val):
                    continue
                peer_vals = []
                for ticker, ratios in peer_ratios.items():
                    peer_metric = ratios.get(metric_key, {})
                    peer_val = peer_metric.get(latest_year, np.nan)
                    if pd.notna(peer_val):
                        peer_vals.append((ticker, float(peer_val)))
                if len(peer_vals) >= 3:
                    chosen = (latest_year, float(company_val), peer_vals)
                    break

            if not chosen:
                continue

            latest_year, company_val, peer_vals = chosen
            peer_stat = float(np.nanmedian([v for _, v in peer_vals]))
            if higher_better:
                position = 'ABOVE' if company_val > peer_stat else 'BELOW'
                deviation = ((company_val - peer_stat) / peer_stat * 100) if peer_stat != 0 else 0
            else:
                position = 'BETTER' if company_val < peer_stat else 'WORSE'
                deviation = ((peer_stat - company_val) / peer_stat * 100) if peer_stat != 0 else 0

            comparisons.append({
                'metric': metric_name,
                'year': latest_year,
                'company_value': company_val,
                'peer_average': peer_stat,
                'position': position,
                'deviation_pct': deviation,
                'peer_count': len(peer_vals),
                'peers_compared': [t for t, _ in peer_vals]
            })

        return {'peers': list(peer_data.keys()), 'comparisons': comparisons}


# ============================================
# FRAUD RISK SCORER
# ============================================

class FraudRiskScorer:
    """
    Advanced Fraud Risk Scoring using Forensic Sigmoid methodology.
    Avoids extreme 0/100 scores for more realistic professional assessment.
    """
    
    # Base risk - no company is perfect (accounts for unknown unknowns)
    BASE_RISK = 8
    
    # Maximum achievable score (leaves room for "off the charts" cases)
    MAX_SCORE = 95
    
    # Severity weights with diminishing returns
    SEVERITY_BASE_WEIGHTS = {
        'CRITICAL': 25,
        'HIGH': 15,
        'MEDIUM': 7,
        'LOW': 2
    }
    
    # Recency multipliers - recent issues matter more
    # CRITICAL issues decay slower (fraud indicators persist longer in memory)
    RECENCY_WEIGHTS = {
        0: 1.5,   # Current year
        1: 1.4,   # 1 year ago
        2: 1.2,   # 2 years ago
        3: 1.0,   # 3 years ago
        4: 0.9,   # 4 years ago
        5: 0.7,   # 5+ years ago
    }
    
    RECENCY_WEIGHTS_CRITICAL = {
        0: 1.5,   # Current year
        1: 1.4,   # 1 year ago
        2: 1.3,   # 2 years ago - CRITICAL decays slower
        3: 1.1,   # 3 years ago
        4: 1.0,   # 4 years ago
        5: 0.85,  # 5+ years ago - still significant for fraud
    }
    
    def calculate_score(self, anomalies, peer_comparison, ratios=None, sector='DEFAULT'):
        """
        Calculate fraud risk score using Forensic Sigmoid methodology.
        """
        raw_score = self.BASE_RISK

        if not anomalies:
            score = self._apply_peer_adjustment(raw_score, peer_comparison)
            return round(score, 1), self._get_risk_level(score, 0, 0)

        current_year_int = 2025
        if ratios and ratios.get('revenue'):
            try:
                years = sorted(ratios['revenue'].keys())
                if years:
                    current_year_int = int(years[-1])
            except Exception:
                pass

        anomaly_groups = {}
        for anomaly in anomalies:
            anomaly_groups.setdefault(anomaly.get('type', 'unknown'), []).append(anomaly)

        severity_order = {'CRITICAL': 0, 'HIGH': 1, 'MEDIUM': 2, 'LOW': 3}
        for group in anomaly_groups.values():
            group.sort(key=lambda x: severity_order.get(x.get('severity', 'LOW'), 3))
            for i, anomaly in enumerate(group):
                severity = anomaly.get('severity', 'LOW')
                base_weight = self.SEVERITY_BASE_WEIGHTS.get(severity, 2)
                diminishing_factor = [1.0, 0.6, 0.4, 0.2][min(i, 3)]
                try:
                    anomaly_year = int(anomaly.get('year', current_year_int))
                    years_ago = max(0, current_year_int - anomaly_year)
                except Exception:
                    years_ago = 3

                if severity == 'CRITICAL':
                    recency_factor = self.RECENCY_WEIGHTS_CRITICAL.get(min(years_ago, 5), 0.85)
                else:
                    recency_factor = self.RECENCY_WEIGHTS.get(min(years_ago, 5), 0.7)

                raw_score += base_weight * diminishing_factor * recency_factor

        score = self._sigmoid_transform(raw_score)
        score = self._apply_peer_adjustment(score, peer_comparison)

        critical_count = sum(1 for a in anomalies if a.get('severity') == 'CRITICAL')
        high_count = sum(1 for a in anomalies if a.get('severity') == 'HIGH')
        risk_level = self._get_risk_level(score, critical_count, high_count)

        return round(score, 1), risk_level

    def _sigmoid_transform(self, raw_score):
        """
        Apply sigmoid-like transformation to raw score.
        Ensures score stays between BASE_RISK and MAX_SCORE.
        """
        # Normalize: map raw_score to 0-1 range
        # Assume raw_score of 100+ would be "maximum risk"
        normalized = min(raw_score / 120, 1.0)
        
        # Apply soft sigmoid curve
        # This gives diminishing returns as score increases
        sigmoid = normalized ** 0.7  # Power < 1 creates concave curve
        
        # Map to final range [BASE_RISK, MAX_SCORE]
        score = self.BASE_RISK + (self.MAX_SCORE - self.BASE_RISK) * sigmoid
        
        return score
    
    def _apply_peer_adjustment(self, score, peer_comparison):
        """Adjust score based on peer comparison."""
        if not peer_comparison or not peer_comparison.get('comparisons'):
            return score
        
        comparisons = peer_comparison['comparisons']
        if not comparisons:
            return score
        
        above_peer_count = sum(1 for c in comparisons if c['position'] in ['ABOVE', 'BETTER'])
        below_peer_count = sum(1 for c in comparisons if c['position'] in ['BELOW', 'WORSE'])
        total = len(comparisons)
        
        if total > 0:
            # Calculate net peer position (-1 to +1)
            net_position = (above_peer_count - below_peer_count) / total
            
            # Adjust score by up to 15% based on peer position
            adjustment = net_position * 0.15 * score
            score = score - adjustment  # Better than peers = lower risk
        
        # Ensure score stays in valid range
        return max(self.BASE_RISK, min(self.MAX_SCORE, score))
    
    def _get_risk_level(self, score, critical_count, high_count):
        """Determine risk level from score and anomaly counts."""
        # Critical if score high OR any critical anomalies in recent years
        if score >= 70 or critical_count >= 2:
            return 'CRITICAL'
        elif score >= 45 or critical_count >= 1 or high_count >= 4:
            return 'HIGH'
        elif score >= 25:
            return 'MEDIUM'
        else:
            return 'LOW'


# ============================================
# REPORT GENERATOR
# ============================================

class ReportGenerator:
    """Generates comprehensive fraud risk report"""
    
    def _generate_specific_reasoning(self, anomalies, ratios, sector):
        """
        Generate a specific one-paragraph reasoning summary based on actual anomalies.
        This addresses the feedback requirement for specific, not generic, explanations.
        """
        if not anomalies:
            return None
        
        # Categorize anomalies by type
        anomaly_types = {}
        for a in anomalies:
            atype = a.get('type', 'unknown')
            if atype not in anomaly_types:
                anomaly_types[atype] = []
            anomaly_types[atype].append(a)
        
        # Build specific reasoning based on what was found
        issues = []
        
        # Revenue-Cash Flow issues
        if 'revenue_cash_divergence' in anomaly_types:
            count = len(anomaly_types['revenue_cash_divergence'])
            issues.append(f"revenue grew significantly faster than cash flow in {count} periods (classic fraud indicator)")
        
        # Bank-specific issues
        if 'bank_profit_collapse' in anomaly_types or 'bank_loss' in anomaly_types:
            losses = anomaly_types.get('bank_loss', [])
            collapses = anomaly_types.get('bank_profit_collapse', [])
            if losses:
                years = [a['year'] for a in losses]
                issues.append(f"bank reported losses in {', '.join(years)} indicating serious asset quality issues")
            elif collapses:
                issues.append(f"sudden profit collapse detected suggesting NPA or provisioning problems")
        
        # Debt issues
        if 'debt_explosion' in anomaly_types:
            count = len(anomaly_types['debt_explosion'])
            issues.append(f"debt exploded abnormally in {count} year(s)")
        
        # Profit quality
        if 'profit_quality_decline' in anomaly_types:
            issues.append("profits are not backed by adequate cash generation")
        
        if 'persistent_profit_quality_issue' in anomaly_types:
            issues.append("persistent gap between reported profits and actual cash flow (major red flag)")
        
        # Related party / Other income
        if 'unusual_other_income' in anomaly_types:
            issues.append("unusual growth in 'Other Income' may indicate related party transactions")
        
        # ROCE decline
        if 'roce_decline' in anomaly_types:
            issues.append("return on capital has been consistently declining")
        
        if not issues:
            return None
        
        # Construct the paragraph
        if len(issues) == 1:
            reasoning = f"Key concern: {issues[0]}."
        elif len(issues) == 2:
            reasoning = f"Key concerns: {issues[0]}, and {issues[1]}."
        else:
            reasoning = f"Key concerns: {', '.join(issues[:-1])}, and {issues[-1]}."
        
        return reasoning
    
    def generate_report(self, company_data, ratios, anomalies, peer_comparison, risk_score, risk_level,
                         auditor_sentiment=None, rpt_growth_data=None):
        """
        Generate complete analysis report fulfilling all deliverables:
        - Fraud risk score with one-paragraph reasoning
        - Anomaly map (deviations from historical trend and peers)
        - Red flag timeline with exact year, statement type, and source reference
        - Auditor note sentiment trend
        - Related party transaction growth chart
        - Industry peer comparison contextualized by sector
        """
        
        report = []
        report.append("=" * 70)
        report.append("                    AUDITGPT FORENSIC ANALYSIS REPORT")
        report.append("=" * 70)
        report.append(f"\nCompany: {company_data.get('name', company_data.get('ticker', 'Unknown'))}")
        report.append(f"Ticker: {company_data.get('ticker', 'N/A')}")
        report.append(f"Sector: {company_data.get('sector', 'Unknown')}")
        report.append(f"Analysis Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Risk Score Summary
        report.append("\n" + "-" * 70)
        report.append("                         FRAUD RISK ASSESSMENT")
        report.append("-" * 70)
        
        risk_emoji = {'CRITICAL': '🔴', 'HIGH': '🟠', 'MEDIUM': '🟡', 'LOW': '🟢'}
        report.append(f"\n{risk_emoji.get(risk_level, '⚪')} FRAUD RISK SCORE: {risk_score}/100 ({risk_level})")
        
        # Risk summary - Generate SPECIFIC reasoning based on anomalies found
        report.append("\n📋 EXECUTIVE SUMMARY:")
        critical_count = sum(1 for a in anomalies if a.get('severity') == 'CRITICAL')
        high_count = sum(1 for a in anomalies if a.get('severity') == 'HIGH')
        medium_count = sum(1 for a in anomalies if a.get('severity') == 'MEDIUM')
        info_count = sum(1 for a in anomalies if a.get('severity') == 'INFO')
        scoring_count = critical_count + high_count + medium_count + sum(1 for a in anomalies if a.get('severity') == 'LOW')
        
        # Generate specific reasoning paragraph
        specific_issues = self._generate_specific_reasoning(anomalies, ratios, company_data.get('sector', 'DEFAULT'))
        
        if risk_level == 'CRITICAL':
            report.append("⚠️  CRITICAL ALERT: This company exhibits severe warning signs.")
            if specific_issues:
                report.append(f"   {specific_issues}")
            else:
                report.append("   Multiple severe red flags detected requiring immediate investigation.")
        elif risk_level == 'HIGH':
            report.append("⚠️  HIGH RISK: Significant anomalies warrant careful scrutiny.")
            if specific_issues:
                report.append(f"   {specific_issues}")
        elif risk_level == 'MEDIUM':
            report.append("📊 MODERATE RISK: Some concerns identified but manageable.")
            if specific_issues:
                report.append(f"   {specific_issues}")
            else:
                report.append("   Continued monitoring recommended.")
        else:
            report.append("✅ LOW RISK: Financial patterns appear healthy.")
            report.append("   No major red flags detected. Company shows stable financial trends.")
        
        report.append(f"\n   Total Alerts Found: {len(anomalies)}")
        report.append(f"   - Scoring alerts: {scoring_count}")
        report.append(f"   - Critical: {critical_count}")
        report.append(f"   - High: {high_count}")
        report.append(f"   - Medium: {medium_count}")
        report.append(f"   - Informational: {info_count}")
        
        # Red Flag Timeline (with statement type and source reference - DELIVERABLE)
        report.append("\n" + "-" * 70)
        report.append("              RED FLAG TIMELINE (WITH DATA REFERENCES)")
        report.append("-" * 70)
        report.append("\n(Each flag includes: Year, Statement Type, and data-source reference)")
        
        if anomalies:
            # Group by year
            by_year = {}
            for a in anomalies:
                year = a.get('year', 'Unknown')
                if year not in by_year:
                    by_year[year] = []
                by_year[year].append(a)
            
            for year in sorted(by_year.keys()):
                report.append(f"\n📅 {year}:")
                for a in by_year[year]:
                    severity_icon = {'CRITICAL': '🔴', 'HIGH': '🟠', 'MEDIUM': '🟡', 'LOW': '🟢', 'INFO': '🟦'}
                    icon = severity_icon.get(a.get('severity', 'LOW'), '⚪')
                    severity = a.get('severity', 'LOW')
                    if severity == 'INFO':
                        report.append(f"   {icon} [INFO] {a.get('description', '')}")
                    else:
                        report.append(f"   {icon} [{severity}] {a.get('description', '')}")
                        report.append(f"      Pattern: {a.get('pattern', 'N/A')}")
                        # Add statement type and source reference (DELIVERABLE: exact filing reference)
                        if a.get('statement_type'):
                            report.append(f"      📄 Statement: {a.get('statement_type')}")
                        if a.get('source_reference'):
                            report.append(f"      📍 Source: {a.get('source_reference')}")
        else:
            report.append("\n✅ No red flags detected in the analysis period.")
        
        # Auditor Note Sentiment Analysis (DELIVERABLE)
        report.append("\n" + "-" * 70)
        report.append("              AUDITOR NOTE SENTIMENT ANALYSIS")
        report.append("-" * 70)
        report.append("\n(Tracks how auditor language changed over the filing history)")
        
        if auditor_sentiment and isinstance(auditor_sentiment, dict) and auditor_sentiment:
            years = sorted(auditor_sentiment.keys())
            report.append("\n📝 Auditor Sentiment Trend:")
            for year in years:
                data = auditor_sentiment[year]
                emoji = {'CRITICAL': '🔴', 'CONCERNING': '🟠', 'NEUTRAL': '🟡', 'STABLE': '🟢'}
                icon = emoji.get(data.get('category', 'NEUTRAL'), '⚪')
                score = data.get('score', 0)
                category = data.get('category', 'NEUTRAL')
                report.append(f"   {year}: {icon} [{category}] Hedging Score: {score}")
                keywords = data.get('hedged_keywords_found', [])
                if keywords:
                    report.append(f"         Keywords detected: {', '.join(keywords[:3])}")
            
            # Trend summary
            if len(years) >= 2:
                first_score = auditor_sentiment[years[0]].get('score', 0)
                last_score = auditor_sentiment[years[-1]].get('score', 0)
                if last_score > first_score + 3:
                    report.append("\n   ⚠️  TREND: Auditor language has become MORE HEDGED over time")
                elif last_score < first_score - 3:
                    report.append("\n   ✅ TREND: Auditor language has become more stable over time")
                else:
                    report.append("\n   ℹ️  TREND: Auditor language sentiment relatively stable")
        else:
            report.append("\n⚠️ Auditor notes not available for sentiment analysis.")
            report.append("   (Full auditor note analysis requires annual report PDF parsing)")
        
        # Related Party Transaction Growth Chart (DELIVERABLE)
        report.append("\n" + "-" * 70)
        report.append("         RELATED PARTY TRANSACTION (RPT) PROXY ANALYSIS")
        report.append("-" * 70)
        report.append("\n(Using 'Other Income' as a conservative proxy where sector-appropriate)")
        
        if rpt_growth_data and isinstance(rpt_growth_data, dict) and rpt_growth_data:
            years = sorted(rpt_growth_data.keys())[-10:]  # Last 10 years
            report.append("\n📊 Other Income vs Revenue Trend:")
            report.append("\n   Year    Other Income    Revenue      OI/Rev %    Trend")
            report.append("   " + "-" * 55)
            
            prev_ratio = None
            for year in years:
                data = rpt_growth_data[year]
                oi = data.get('other_income', 0)
                rev = data.get('revenue', 0)
                ratio = data.get('oi_to_revenue_pct', 0)
                
                # Determine trend arrow
                if prev_ratio is not None:
                    if ratio > prev_ratio + 2:
                        trend = '↑ UP'
                    elif ratio < prev_ratio - 2:
                        trend = '↓ DOWN'
                    else:
                        trend = '→ STABLE'
                else:
                    trend = '-'
                
                report.append(f"   {year}    ₹{oi:>10,.0f}    ₹{rev:>10,.0f}    {ratio:>6.1f}%    {trend}")
                prev_ratio = ratio
            
            # Flag unusual jumps
            rpt_anomalies = [a for a in anomalies if a.get('type') == 'unusual_other_income']
            if rpt_anomalies:
                report.append("\n   ⚠️  FLAGGED JUMPS:")
                for a in rpt_anomalies:
                    report.append(f"      - {a.get('year')}: {a.get('description')}")
                    if a.get('source_reference'):
                        report.append(f"        Source: {a.get('source_reference')}")
        else:
            report.append("\nOther Income/RPT proxy data not available.")
        
        # Peer Comparison
        report.append("\n" + "-" * 70)
        report.append("                       INDUSTRY PEER COMPARISON")
        report.append("-" * 70)
        
        if peer_comparison and peer_comparison.get('peers'):
            report.append(f"\nPeers Analyzed: {', '.join(peer_comparison['peers'])}")
            report.append("\nMetric Comparison:")
            
            for comp in peer_comparison.get('comparisons', []):
                position_icon = '✅' if comp['position'] in ['ABOVE', 'BETTER'] else '⚠️'
                report.append(f"\n   {comp['metric']}:")
                report.append(f"      Company: {comp['company_value']:.2f}")
                report.append(f"      Peer Median: {comp['peer_average']:.2f}")
                report.append(f"      {position_icon} Position: {comp['position']} peers by {abs(comp['deviation_pct']):.1f}%")
        else:
            report.append("\n⚠️ Peer comparison data not available.")
        
        # Key Financial Trends
        report.append("\n" + "-" * 70)
        report.append("                        KEY FINANCIAL TRENDS")
        report.append("-" * 70)
        
        # Revenue trend
        if 'revenue' in ratios:
            rev = ratios['revenue']
            years = sorted(rev.keys())[-5:]
            report.append("\n📈 Revenue (Last 5 Years):")
            for y in years:
                report.append(f"   {y}: ₹{rev[y]:,.0f} Cr")
        
        # Profit trend
        if 'net_profit' in ratios:
            profit = ratios['net_profit']
            years = sorted(profit.keys())[-5:]
            report.append("\n📈 Net Profit (Last 5 Years):")
            for y in years:
                report.append(f"   {y}: ₹{profit[y]:,.0f} Cr")
        
        # CFO trend
        if 'cash_from_operations' in ratios:
            cfo = ratios['cash_from_operations']
            years = sorted(cfo.keys())[-5:]
            report.append("\n💰 Cash from Operations (Last 5 Years):")
            for y in years:
                report.append(f"   {y}: ₹{cfo[y]:,.0f} Cr")
        
        report.append("\n" + "=" * 70)
        report.append("                         END OF REPORT")
        report.append("=" * 70)
        
        return "\n".join(report)


# ============================================
# MAIN AUDITGPT ENGINE
# ============================================

class AuditGPT:
    """
    Main AuditGPT Forensic Analysis Engine
    
    Fulfills all deliverables from the problem statement:
    1. Working prototype accepting any NSE-listed company name
    2. Automated filing ingestion pipeline
    3. Live demo under 90 seconds
    4. Industry peer benchmarking (5+ companies)
    5. Auditor note sentiment analysis
    6. Every red flag with exact filing year, statement type, and source reference
    7. Industry-specific anomaly contextualization
    """
    
    def __init__(self):
        self.data_acq = DataAcquisition()
        self.anomaly_detector = AnomalyDetector(INDUSTRY_NORMS)
        self.peer_benchmark = PeerBenchmark(self.data_acq)
        self.risk_scorer = FraudRiskScorer()
        self.report_gen = ReportGenerator()
        self.sentiment_analyzer = AuditorSentimentAnalyzer()
    
    def _generate_mock_auditor_sentiment(self, data, anomalies):
        """
        Prefer actual parsed auditor notes. If notes are unavailable, return empty data
        instead of fabricating sentiment from anomalies.
        """
        notes_data = data.get('auditor_notes') or {}
        if not isinstance(notes_data, dict) or not notes_data:
            return {}
        return self.sentiment_analyzer.analyze_sentiment_trend(notes_data)

    def analyze(self, ticker, verbose=True):
        """Run complete forensic analysis on a company"""
        
        if verbose:
            print(f"\n🔍 AUDITGPT: Starting forensic analysis for {ticker}...")
        
        # Step 1: Fetch data
        if verbose:
            print("   📥 Fetching 10-year financial data...")
        
        data = self.data_acq.fetch_company_data(ticker)
        if not data:
            print(f"   ❌ Failed to fetch data for {ticker}")
            return None
        
        if verbose:
            print(f"   ✅ Data fetched: {data.get('name', ticker)}")
            print(f"   📊 Sector identified: {data.get('sector', 'Unknown')}")
        
        # Step 2: Calculate ratios
        if verbose:
            print("   📐 Calculating financial ratios...")
        
        ratios = RatioCalculator.calculate_ratios(data)
        
        # Step 3: Detect anomalies
        if verbose:
            print("   🔎 Running anomaly detection...")
        
        sector = data.get('sector', 'DEFAULT')
        anomalies = self.anomaly_detector.detect_anomalies(data, ratios, sector)
        
        if verbose:
            print(f"   ⚠️  Found {len(anomalies)} anomalies")
        
        # Step 4: Peer benchmarking
        if verbose:
            print("   📊 Benchmarking against industry peers...")
        
        peer_comparison = self.peer_benchmark.benchmark(data, ratios, sector)
        
        if verbose and peer_comparison.get('peers'):
            print(f"   ✅ Compared with {len(peer_comparison['peers'])} peers")
        
        # Step 5: Calculate risk score (with sigmoid methodology)
        if verbose:
            print("   🎯 Calculating fraud risk score...")
        
        # Filter out INFO-level anomalies (structural breaks) for scoring
        scoring_anomalies = [a for a in anomalies if a.get('severity') != 'INFO']
        risk_score, risk_level = self.risk_scorer.calculate_score(scoring_anomalies, peer_comparison, ratios, sector)
        
        # Step 6: Auditor Sentiment Analysis (DELIVERABLE)
        if verbose:
            print("   📝 Analyzing auditor note sentiment (only if parsed notes are available)...")
        
        auditor_sentiment = self._generate_mock_auditor_sentiment(data, anomalies)
        
        # Step 7: Get RPT Growth Data (DELIVERABLE)
        rpt_growth_data = self.anomaly_detector.get_rpt_growth_chart_data()
        
        # Step 8: Generate report
        if verbose:
            print("   📝 Generating forensic report...\n")
        
        report = self.report_gen.generate_report(
            data, ratios, anomalies, peer_comparison, risk_score, risk_level,
            auditor_sentiment=auditor_sentiment,
            rpt_growth_data=rpt_growth_data
        )
        
        return {
            'ticker': ticker,
            'name': data.get('name'),
            'sector': sector,
            'risk_score': risk_score,
            'risk_level': risk_level,
            'anomalies': anomalies,
            'peer_comparison': peer_comparison,
            'ratios': ratios,
            'auditor_sentiment': auditor_sentiment,
            'rpt_growth_data': rpt_growth_data,
            'report': report
        }


# ============================================
# MAIN EXECUTION
# ============================================

if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("          AUDITGPT - FINANCIAL STATEMENT FORENSICS ENGINE")
    print("   'The AI That Finds What the Auditors Missed'")
    print("=" * 70)
    
    # Initialize engine
    engine = AuditGPT()
    
    # Demo with known fraud case
    print("\n📌 DEMO: Analyzing YES BANK (known fraud case)")
    print("-" * 50)
    
    result = engine.analyze("YESBANK")
    if result:
        print(result['report'])
        
        # Save report
        with open("YESBANK_audit_report.txt", 'w') as f:
            f.write(result['report'])
        print("\n💾 Report saved to YESBANK_audit_report.txt")
    
    # Interactive mode
    print("\n" + "=" * 70)
    user_input = input("🔍 Enter company ticker for live analysis (or press Enter to skip): ").upper().strip()
    
    if user_input:
        result = engine.analyze(user_input)
        if result:
            print(result['report'])
            
            # Save report
            filename = f"{user_input}_audit_report.txt"
            with open(filename, 'w') as f:
                f.write(result['report'])
            print(f"\n💾 Report saved to {filename}")
    
    print("\n🎯 AUDITGPT Analysis Complete.")
