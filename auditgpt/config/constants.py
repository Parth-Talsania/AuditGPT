"""
Constants and configuration for AuditGPT forensic analysis.

These constants define fraud patterns, industry norms, sector mappings,
and peer universes used throughout the analysis pipeline.
"""

from typing import Dict, List, Any

# Fraud precursor patterns based on historical cases (Satyam, Yes Bank, IL&FS, DHFL)
FRAUD_PATTERNS: Dict[str, Dict[str, Any]] = {
    'revenue_cash_divergence': {
        'description': 'Revenue growing faster than operating cash flow',
        'threshold': 0.3,  # 30% divergence over 3 years
        'weight': 0.25,
        'manipulation_or_stress': 'manipulation',
    },
    'debt_explosion': {
        'description': 'Debt growing faster than assets',
        'threshold': 0.5,  # 50% faster
        'weight': 0.20,
        'manipulation_or_stress': 'stress',
    },
    'working_capital_deterioration': {
        'description': 'Working capital days increasing significantly',
        'threshold': 0.4,  # 40% increase
        'weight': 0.15,
        'manipulation_or_stress': 'stress',
    },
    'profit_quality_decline': {
        'description': 'Net profit growing but cash from operations declining',
        'threshold': 0.25,
        'weight': 0.20,
        'manipulation_or_stress': 'manipulation',
    },
    'roce_decline': {
        'description': 'Return on capital employed declining consistently',
        'threshold': -0.2,  # 20% decline
        'weight': 0.10,
        'manipulation_or_stress': 'stress',
    },
    'debtor_days_spike': {
        'description': 'Debtor days increasing abnormally',
        'threshold': 0.3,  # 30% increase
        'weight': 0.10,
        'manipulation_or_stress': 'manipulation',
    },
    'npa_spike': {
        'description': 'Non-performing assets spiking (banks)',
        'threshold': 0.5,  # 50% increase
        'weight': 0.25,
        'manipulation_or_stress': 'stress',
    },
    'auditor_language_escalation': {
        'description': 'Auditor notes becoming more hedged/qualified',
        'threshold': 3,  # Score increase
        'weight': 0.15,
        'manipulation_or_stress': 'manipulation',
    },
}

# Industry-specific thresholds
INDUSTRY_NORMS: Dict[str, Dict[str, float]] = {
    'IT': {
        'debt_equity_max': 0.5,
        'current_ratio_min': 1.5,
        'roce_min': 20,
        'debtor_days_max': 90,
        'opm_min': 15,
        'interest_coverage_min': 10,
    },
    'BANK': {
        'debt_equity_max': 15,  # Banks have high leverage by design
        'current_ratio_min': 0.8,
        'roce_min': 8,
        'npa_max': 5,
        'nnpa_max': 3,
        'car_min': 12,  # Capital Adequacy Ratio
        'provision_coverage_min': 60,  # Provision Coverage Ratio
    },
    'NBFC': {
        'debt_equity_max': 6,
        'current_ratio_min': 1.0,
        'roce_min': 10,
        'npa_max': 4,
        'car_min': 15,
    },
    'PHARMA': {
        'debt_equity_max': 1.0,
        'current_ratio_min': 1.2,
        'roce_min': 15,
        'rd_sales_min': 5,  # R&D to sales
        'opm_min': 12,
    },
    'INFRA': {
        'debt_equity_max': 2.5,  # Infrastructure can have higher debt
        'current_ratio_min': 1.0,
        'roce_min': 10,
        'debtor_days_max': 120,
        'interest_coverage_min': 2,
    },
    'REALTY': {
        'debt_equity_max': 1.5,
        'current_ratio_min': 1.2,
        'roce_min': 8,
        'debtor_days_max': 180,  # Realty has long collection cycles
        'interest_coverage_min': 1.5,
    },
    'AUTO': {
        'debt_equity_max': 1.0,
        'current_ratio_min': 1.0,
        'roce_min': 12,
        'debtor_days_max': 45,
        'opm_min': 10,
    },
    'FMCG': {
        'debt_equity_max': 0.5,
        'current_ratio_min': 1.0,
        'roce_min': 25,
        'debtor_days_max': 30,
        'opm_min': 15,
    },
    'METAL': {
        'debt_equity_max': 1.5,
        'current_ratio_min': 1.0,
        'roce_min': 10,
        'debtor_days_max': 60,
        'interest_coverage_min': 3,
    },
    'ENERGY': {
        'debt_equity_max': 1.5,
        'current_ratio_min': 1.0,
        'roce_min': 10,
        'debtor_days_max': 60,
        'interest_coverage_min': 3,
    },
    'FINANCE': {
        'debt_equity_max': 8,
        'current_ratio_min': 1.0,
        'roce_min': 10,
        'npa_max': 4,
    },
    'DEFAULT': {
        'debt_equity_max': 1.5,
        'current_ratio_min': 1.2,
        'roce_min': 12,
        'debtor_days_max': 90,
        'opm_min': 10,
        'interest_coverage_min': 3,
    }
}

# Sector mapping from Nifty indices
SECTOR_MAPPING: Dict[str, str] = {
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
    'Nifty Financial Services 25/50': 'FINANCE',
    # Direct ticker-to-sector mapping for common companies
    'HDFCBANK': 'BANK',
    'ICICIBANK': 'BANK',
    'KOTAKBANK': 'BANK',
    'AXISBANK': 'BANK',
    'SBIN': 'BANK',
    'PNB': 'BANK',
    'BANKBARODA': 'BANK',
    'YESBANK': 'BANK',
    'INDUSINDBK': 'BANK',
    'FEDERALBNK': 'BANK',
    'IDFCFIRSTB': 'BANK',
    'CANBK': 'BANK',
    'UNIONBANK': 'BANK',
    'INDIANB': 'BANK',
    'BANKINDIA': 'BANK',
    'TCS': 'IT',
    'INFY': 'IT',
    'WIPRO': 'IT',
    'HCLTECH': 'IT',
    'TECHM': 'IT',
    'LTIM': 'IT',
    'SUNPHARMA': 'PHARMA',
    'DRREDDY': 'PHARMA',
    'CIPLA': 'PHARMA',
    'DLF': 'REALTY',
    'GODREJPROP': 'REALTY',
    'LT': 'INFRA',
    'RELIANCE': 'ENERGY',
    'ONGC': 'ENERGY',
    'BAJFINANCE': 'FINANCE',
    'MUTHOOTFIN': 'FINANCE',
}

# Peer universes - separated by sub-industry for accurate comparison
PEER_UNIVERSES: Dict[str, Dict[str, List[str]]] = {
    'BANK': {
        'private': ['HDFCBANK', 'ICICIBANK', 'KOTAKBANK', 'AXISBANK', 'INDUSINDBK', 'FEDERALBNK', 'IDFCFIRSTB'],
        'psu': ['SBIN', 'PNB', 'BANKBARODA', 'CANBK', 'UNIONBANK', 'INDIANB', 'BANKINDIA'],
        'all': ['HDFCBANK', 'ICICIBANK', 'KOTAKBANK', 'AXISBANK', 'SBIN', 'PNB', 'BANKBARODA', 'YESBANK'],
    },
    'IT': {
        'large_cap': ['TCS', 'INFY', 'WIPRO', 'HCLTECH', 'TECHM', 'LTIM'],
        'mid_cap': ['MPHASIS', 'COFORGE', 'PERSISTENT', 'LTTS', 'TATAELXSI'],
        'all': ['TCS', 'INFY', 'WIPRO', 'HCLTECH', 'TECHM', 'LTIM'],
    },
    'PHARMA': {
        'large_cap': ['SUNPHARMA', 'DRREDDY', 'CIPLA', 'DIVISLAB', 'LUPIN'],
        'mid_cap': ['AUROPHARMA', 'ALKEM', 'TORNTPHARM', 'BIOCON', 'GLAND'],
        'all': ['SUNPHARMA', 'DRREDDY', 'CIPLA', 'DIVISLAB', 'LUPIN'],
    },
    'INFRA': {
        'all': ['LT', 'ADANIENT', 'ADANIPORTS', 'POWERGRID', 'NTPC', 'RVNL'],
    },
    'REALTY': {
        'all': ['DLF', 'GODREJPROP', 'OBEROIRLTY', 'PRESTIGE', 'BRIGADE', 'SOBHA'],
    },
    'AUTO': {
        'oem': ['MARUTI', 'TATAMOTORS', 'M&M', 'BAJAJ-AUTO', 'HEROMOTOCO', 'EICHERMOT'],
        'ancillary': ['MOTHERSON', 'BOSCHLTD', 'BALKRISIND', 'MRF'],
        'all': ['MARUTI', 'TATAMOTORS', 'M&M', 'BAJAJ-AUTO', 'HEROMOTOCO'],
    },
    'FMCG': {
        'all': ['HINDUNILVR', 'ITC', 'NESTLEIND', 'BRITANNIA', 'DABUR', 'MARICO', 'COLPAL'],
    },
    'METAL': {
        'all': ['TATASTEEL', 'JSWSTEEL', 'HINDALCO', 'VEDL', 'COALINDIA', 'NMDC'],
    },
    'ENERGY': {
        'all': ['RELIANCE', 'ONGC', 'IOC', 'BPCL', 'GAIL', 'NTPC'],
    },
    'NBFC': {
        'all': ['BAJFINANCE', 'BAJAJFINSV', 'CHOLAFIN', 'MUTHOOTFIN', 'SHRIRAMFIN', 'M&MFIN'],
    },
    'FINANCE': {
        'all': ['BAJFINANCE', 'BAJAJFINSV', 'CHOLAFIN', 'HDFCAMC', 'ICICIGI', 'SBILIFE'],
    },
    'DEFAULT': {
        'all': [],
    },
}

# Auditor sentiment keywords
AUDITOR_RED_FLAG_WORDS: List[str] = [
    'subject to', 'uncertainty', 'material misstatement', 
    'emphasis of matter', 'except for', 'adverse', 'going concern',
    'discrepancy', 'fraud', 'restate', 'restated', 'restatement',
    'qualified opinion', 'disclaimer', 'limitation', 'unable to',
    'significant doubt', 'material weakness', 'deficiency',
    'non-compliance', 'deviation', 'irregularity', 'manipulation',
    'overstatement', 'understatement', 'contingent liability',
    'pending litigation', 'related party', 'suspicious'
]

AUDITOR_STABLE_WORDS: List[str] = [
    'true and fair view', 'unmodified', 'compliance', 
    'materially correct', 'fair presentation', 'unqualified',
    'clean opinion', 'properly maintained', 'adequate disclosure',
    'in accordance with', 'fairly represents', 'no material'
]

# Sectors that are classified as banking/financial
BANK_SECTORS = {'BANK', 'NBFC', 'FINANCE'}

# Legacy PEER_GROUPS for backward compatibility
PEER_GROUPS: Dict[str, List[str]] = {
    'BANK': ['HDFCBANK', 'ICICIBANK', 'KOTAKBANK', 'AXISBANK', 'SBIN', 'PNB', 'BANKBARODA'],
    'IT': ['TCS', 'INFY', 'WIPRO', 'HCLTECH', 'TECHM', 'LTIM'],
    'PHARMA': ['SUNPHARMA', 'DRREDDY', 'CIPLA', 'DIVISLAB', 'LUPIN'],
    'INFRA': ['LT', 'ADANIENT', 'ADANIPORTS', 'POWERGRID', 'NTPC'],
    'REALTY': ['DLF', 'GODREJPROP', 'OBEROIRLTY', 'PRESTIGE', 'BRIGADE'],
    'AUTO': ['MARUTI', 'TATAMOTORS', 'M&M', 'BAJAJ-AUTO', 'HEROMOTOCO'],
    'FMCG': ['HINDUNILVR', 'ITC', 'NESTLEIND', 'BRITANNIA', 'DABUR'],
    'METAL': ['TATASTEEL', 'JSWSTEEL', 'HINDALCO', 'VEDL', 'COALINDIA'],
    'ENERGY': ['RELIANCE', 'ONGC', 'IOC', 'BPCL', 'GAIL'],
    'NBFC': ['BAJFINANCE', 'BAJAJFINSV', 'CHOLAFIN', 'MUTHOOTFIN', 'SHRIRAMFIN'],
    'DEFAULT': [],
}

# Severity weights for scoring
SEVERITY_WEIGHTS: Dict[str, int] = {
    'CRITICAL': 25,
    'HIGH': 15,
    'MEDIUM': 7,
    'LOW': 2,
}

# Recency weights for scoring (years ago -> weight)
RECENCY_WEIGHTS: Dict[int, float] = {
    0: 1.5,   # Current year
    1: 1.4,   # 1 year ago
    2: 1.2,   # 2 years ago
    3: 1.0,   # 3 years ago
    4: 0.9,   # 4 years ago
    5: 0.7,   # 5+ years ago
}

# Critical issues decay slower
RECENCY_WEIGHTS_CRITICAL: Dict[int, float] = {
    0: 1.5,
    1: 1.4,
    2: 1.3,
    3: 1.1,
    4: 1.0,
    5: 0.85,
}
