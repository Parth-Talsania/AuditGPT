"""
Sector-specific threshold configurations for AuditGPT.

Provides dynamic threshold lookups based on sector classification.
"""

from typing import Dict, Optional, Any
from dataclasses import dataclass

from auditgpt.config.constants import INDUSTRY_NORMS


@dataclass
class ThresholdSet:
    """A set of thresholds for a specific sector."""
    sector: str
    debt_equity_max: float
    current_ratio_min: float
    roce_min: float
    debtor_days_max: Optional[float] = None
    opm_min: Optional[float] = None
    npa_max: Optional[float] = None
    nnpa_max: Optional[float] = None
    car_min: Optional[float] = None
    provision_coverage_min: Optional[float] = None
    interest_coverage_min: Optional[float] = None
    rd_sales_min: Optional[float] = None


class SectorThresholds:
    """
    Manages sector-specific thresholds for anomaly detection.
    
    Ensures every alert is sector-aware, avoiding one-size-fits-all thresholds.
    """
    
    def __init__(self):
        self._norms = INDUSTRY_NORMS
    
    def get_threshold(self, sector: str, metric: str, default: Optional[float] = None) -> Optional[float]:
        """
        Get a specific threshold for a sector.
        
        Args:
            sector: The sector code (e.g., 'BANK', 'IT')
            metric: The metric name (e.g., 'debt_equity_max', 'npa_max')
            default: Default value if not found
            
        Returns:
            The threshold value or default
        """
        sector_norms = self._norms.get(sector, self._norms['DEFAULT'])
        return sector_norms.get(metric, default)
    
    def get_threshold_set(self, sector: str) -> ThresholdSet:
        """
        Get all thresholds for a sector as a ThresholdSet.
        
        Args:
            sector: The sector code
            
        Returns:
            ThresholdSet with all applicable thresholds
        """
        norms = self._norms.get(sector, self._norms['DEFAULT'])
        
        return ThresholdSet(
            sector=sector,
            debt_equity_max=norms.get('debt_equity_max', 1.5),
            current_ratio_min=norms.get('current_ratio_min', 1.2),
            roce_min=norms.get('roce_min', 12),
            debtor_days_max=norms.get('debtor_days_max'),
            opm_min=norms.get('opm_min'),
            npa_max=norms.get('npa_max'),
            nnpa_max=norms.get('nnpa_max'),
            car_min=norms.get('car_min'),
            provision_coverage_min=norms.get('provision_coverage_min'),
            interest_coverage_min=norms.get('interest_coverage_min'),
            rd_sales_min=norms.get('rd_sales_min'),
        )
    
    def is_banking_sector(self, sector: str) -> bool:
        """Check if sector is banking/finance (different analysis rules apply)."""
        return sector in ('BANK', 'NBFC', 'FINANCE')
    
    def should_skip_cfo_analysis(self, sector: str) -> bool:
        """
        Determine if CFO-based analysis should be skipped for a sector.
        
        Banks have different cash flow dynamics where loans are cash outflows,
        so CFO divergence analysis creates false positives.
        """
        return sector in ('BANK', 'NBFC')
    
    def should_skip_rpt_proxy(self, sector: str) -> bool:
        """
        Determine if Other Income as RPT proxy should be skipped.
        
        For BANK and FINANCE sectors, Other Income has different meaning
        and should not be used as a proxy for related-party transactions.
        """
        return sector in ('BANK', 'FINANCE', 'NBFC')
    
    def get_peer_comparison_multiplier(self, sector: str, metric: str) -> float:
        """
        Get the multiplier for peer comparison (how far above norm is concerning).
        
        Returns multiplier where company_value > norm * multiplier triggers alert.
        """
        # Banks have naturally higher leverage, so use tighter multipliers
        if sector == 'BANK' and metric == 'debt_equity_max':
            return 1.2
        # Infra can have legitimate higher debt
        if sector == 'INFRA' and metric == 'debt_equity_max':
            return 1.5
        # Default: 1.5x norm is concerning
        return 1.5


# Standalone helper functions for convenience

def should_skip_cfo_analysis(sector: str) -> bool:
    """
    Determine if CFO-based analysis should be skipped for a sector.
    
    Banks have different cash flow dynamics where loans are cash outflows,
    so CFO divergence analysis creates false positives.
    """
    return sector in ('BANK', 'NBFC')


def should_skip_rpt_proxy(sector: str) -> bool:
    """
    Determine if Other Income as RPT proxy should be skipped.
    
    For BANK and FINANCE sectors, Other Income has different meaning
    and should not be used as a proxy for related-party transactions.
    """
    return sector in ('BANK', 'FINANCE', 'NBFC')


def is_banking_sector(sector: str) -> bool:
    """Check if sector is banking/finance (different analysis rules apply)."""
    return sector in ('BANK', 'NBFC', 'FINANCE')

