"""
Pytest configuration and shared fixtures for AuditGPT tests.
"""

import pytest
import json
import os
from pathlib import Path

# Add auditgpt to path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from auditgpt.signals.base import Signal, SignalSeverity, SignalCategory, SignalFamily, create_signal
from auditgpt.evidence.models import EvidenceRef, RefType
from auditgpt.scoring.dual_scorer import DualScorer, DualScore


# Fixture directory
FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def healthy_it_company_data():
    """Test data for a healthy IT company (like TCS)."""
    return {
        'company': 'TCS',
        'sector': 'IT',
        'years': [2020, 2021, 2022, 2023, 2024],
        'pnl': {
            'Revenue': [150000, 165000, 180000, 200000, 220000],
            'Net Profit': [30000, 33000, 36000, 40000, 44000],
            'Operating Profit': [40000, 44000, 48000, 53000, 58000],
            'Other Income': [2000, 2200, 2400, 2600, 2800],
            'Profit Before Tax': [42000, 46000, 50000, 55000, 60000],
        },
        'balance_sheet': {
            'Trade Receivables': [25000, 27000, 29000, 32000, 35000],
            'Borrowings': [5000, 5500, 6000, 6500, 7000],
            'Share Capital': [100000, 110000, 120000, 130000, 140000],
        },
        'cash_flow': {
            'Cash from Operating Activity': [35000, 38000, 42000, 46000, 50000],
        },
    }


@pytest.fixture
def stressed_bank_data():
    """Test data for a stressed bank (like YESBANK)."""
    return {
        'company': 'YESBANK',
        'sector': 'BANK',
        'years': [2020, 2021, 2022, 2023, 2024],
        'pnl': {
            'Revenue': [25000, 24000, 22000, 21000, 20000],
            'Net Profit': [2000, -16000, -4000, 1000, 500],
            'Net Interest Income': [8000, 6000, 5000, 5500, 5000],
            'Operating Profit': [4000, -10000, -2000, 2000, 1500],
            'GNPA %': [3.0, 16.8, 14.0, 12.0, 9.0],
            'NNPA %': [1.5, 5.0, 4.5, 4.0, 3.5],
            'NIM %': [3.2, 2.0, 1.8, 2.0, 2.1],
        },
        'balance_sheet': {
            'CAR %': [16.0, 8.0, 10.0, 12.0, 14.0],
            'Total Deposits': [200000, 150000, 160000, 170000, 175000],
            'Advances': [180000, 140000, 145000, 150000, 155000],
        },
        'cash_flow': {
            'Cash from Operating Activity': [5000, -20000, 3000, 5000, 4000],
        },
    }


@pytest.fixture
def negative_cfo_company_data():
    """Test data for a company with negative/unstable CFO."""
    return {
        'company': 'NEGCFO',
        'sector': 'DEFAULT',
        'years': [2020, 2021, 2022, 2023, 2024],
        'pnl': {
            'Revenue': [10000, 12000, 14000, 15000, 16000],
            'Net Profit': [1000, 1500, 1800, 2000, 2200],
        },
        'balance_sheet': {
            'Trade Receivables': [2000, 3000, 5000, 7000, 10000],
            'Borrowings': [5000, 6000, 7000, 8000, 9000],
            'Share Capital': [10000, 10000, 10000, 10000, 10000],
        },
        'cash_flow': {
            'Cash from Operating Activity': [-500, 0, -1000, 500, -200],
        },
    }


@pytest.fixture
def sample_signal_manipulation():
    """Sample manipulation signal."""
    return create_signal(
        family=SignalFamily.REVENUE_DIVERGENCE,
        category=SignalCategory.MANIPULATION,
        year=2024,
        severity=SignalSeverity.HIGH,
        description="Revenue grew 25% while CFO declined 15%, indicating potential quality issues",
        evidence_refs=[
            EvidenceRef(
                ref_type=RefType.STATEMENT,
                filing_year=2024,
                statement_type="P&L",
                line_item="Revenue",
                snippet="Revenue grew 25% vs CFO -15%",
            )
        ],
    )


@pytest.fixture
def sample_signal_stress():
    """Sample stress signal."""
    return create_signal(
        family=SignalFamily.LEVERAGE_STRESS,
        category=SignalCategory.STRESS,
        year=2024,
        severity=SignalSeverity.MEDIUM,
        description="Debt/Equity ratio of 2.5 exceeds sector norm of 1.5",
        evidence_refs=[
            EvidenceRef(
                ref_type=RefType.RATIO,
                filing_year=2024,
                snippet="D/E = 2.5, above sector norm of 1.5",
            )
        ],
    )


@pytest.fixture
def dual_scorer():
    """Dual scorer instance."""
    return DualScorer()


@pytest.fixture
def evidence_store():
    """Empty evidence store."""
    from auditgpt.evidence.store import EvidenceStore
    return EvidenceStore()


def load_fixture(name: str) -> dict:
    """Load a JSON fixture file."""
    fixture_path = FIXTURES_DIR / f"{name}.json"
    if fixture_path.exists():
        with open(fixture_path) as f:
            return json.load(f)
    return {}
