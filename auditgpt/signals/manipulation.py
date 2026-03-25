"""
Manipulation/fraud-risk signal detection for AuditGPT.

Detects signals that may indicate accounting manipulation or fraud:
- Revenue vs CFO divergence
- Profit quality issues
- Receivables spikes
- Unusual related-party growth
- Auditor language escalation
- One-time gain dependence
"""

from typing import List, Dict, Any, Optional
import numpy as np

from auditgpt.signals.base import (
    Signal, SignalFamily, SignalCategory, SignalSeverity, create_signal
)
from auditgpt.evidence.models import EvidenceRef, RefType, create_statement_evidence
from auditgpt.config.constants import FRAUD_PATTERNS
from auditgpt.config.thresholds import SectorThresholds


class ManipulationSignalDetector:
    """
    Detects manipulation/fraud-risk signals in financial data.
    
    These signals suggest potential accounting manipulation rather than
    genuine business stress.
    """
    
    def __init__(self, thresholds: Optional[SectorThresholds] = None):
        self.thresholds = thresholds or SectorThresholds()
        self.structural_break_years: set = set()
    
    def set_structural_breaks(self, years: set):
        """Set years that are structural breaks (mergers/acquisitions)."""
        self.structural_break_years = years
    
    def detect_all(
        self,
        data: Dict[str, Any],
        ratios: Dict[str, Any],
        sector: str = 'DEFAULT'
    ) -> List[Signal]:
        """
        Run all manipulation signal detectors.
        
        Args:
            data: Company financial data dict
            ratios: Calculated financial ratios
            sector: Company sector code
            
        Returns:
            List of detected manipulation signals
        """
        signals = []
        
        # Skip CFO-based analysis for banks (loans are cash outflows)
        if not self.thresholds.should_skip_cfo_analysis(sector):
            signals.extend(self._check_revenue_cfo_divergence(ratios))
            signals.extend(self._check_profit_quality(ratios))
        
        # Receivables/debtor analysis (skip for banks)
        if not self.thresholds.is_banking_sector(sector):
            signals.extend(self._check_receivables_spike(ratios, sector))
        
        # Other income / one-time gains (skip proxy for banks)
        if not self.thresholds.should_skip_rpt_proxy(sector):
            signals.extend(self._check_one_time_gain_dependence(data, ratios, sector))
        
        return signals
    
    def _check_revenue_cfo_divergence(self, ratios: Dict[str, Any]) -> List[Signal]:
        """
        Check if revenue grows faster than cash flow.
        
        FIX: Properly handle non-positive CFO baselines.
        """
        signals = []
        
        rev_growth = ratios.get('revenue_growth', {})
        cfo = ratios.get('cash_from_operations', {})
        revenue = ratios.get('revenue', {})
        
        if not rev_growth or not cfo or not revenue:
            return signals
        
        years = sorted(set(rev_growth.keys()) & set(cfo.keys()))
        
        for i in range(2, len(years)):
            year = years[i]
            
            # Skip structural break years
            if year in self.structural_break_years:
                continue
            
            # Get 3-year values
            base_year = years[i-2]
            
            rev_start = revenue.get(base_year, 0)
            rev_end = revenue.get(year, 0)
            cfo_start = cfo.get(base_year, 0)
            cfo_end = cfo.get(year, 0)
            
            # Skip if revenue baseline is invalid
            if rev_start <= 0:
                continue
            
            rev_3yr_growth = (rev_end - rev_start) / rev_start
            
            # FIX: Skip comparison if CFO baseline is non-positive
            # This avoids bogus -100% growth calculations
            if cfo_start <= 0:
                # Only flag if current CFO is also negative with growing revenue
                if cfo_end < 0 and rev_3yr_growth > 0.2:
                    evidence = [
                        create_statement_evidence('P&L', 'Revenue', year, rev_end),
                        create_statement_evidence('Cash Flow', 'CFO', year, cfo_end),
                    ]
                    
                    signals.append(create_signal(
                        family=SignalFamily.REVENUE_DIVERGENCE,
                        category=SignalCategory.MANIPULATION,
                        year=year,
                        severity=SignalSeverity.HIGH,
                        description=f"Revenue grew {rev_3yr_growth*100:.1f}% over 3 years while CFO remained negative",
                        evidence_refs=evidence,
                        pattern=FRAUD_PATTERNS['revenue_cash_divergence']['description'],
                        confidence=0.7,  # Lower confidence due to edge case
                        anomaly_type='revenue_cash_divergence',
                    ))
                continue
            
            cfo_3yr_growth = (cfo_end - cfo_start) / cfo_start
            
            # Check for significant divergence
            if rev_3yr_growth > 0.2 and cfo_3yr_growth < rev_3yr_growth - 0.3:
                divergence = rev_3yr_growth - cfo_3yr_growth
                
                severity = SignalSeverity.HIGH if divergence > 0.5 else SignalSeverity.MEDIUM
                
                evidence = [
                    create_statement_evidence('P&L', 'Revenue', base_year, rev_start),
                    create_statement_evidence('P&L', 'Revenue', year, rev_end),
                    create_statement_evidence('Cash Flow', 'CFO', base_year, cfo_start),
                    create_statement_evidence('Cash Flow', 'CFO', year, cfo_end),
                ]
                
                signals.append(create_signal(
                    family=SignalFamily.REVENUE_DIVERGENCE,
                    category=SignalCategory.MANIPULATION,
                    year=year,
                    severity=severity,
                    description=f"Revenue grew {rev_3yr_growth*100:.1f}% but CFO grew only {cfo_3yr_growth*100:.1f}% over 3 years",
                    evidence_refs=evidence,
                    pattern=FRAUD_PATTERNS['revenue_cash_divergence']['description'],
                    confidence=0.85,
                    anomaly_type='revenue_cash_divergence',
                    company_comparison=f"3-year divergence of {divergence*100:.0f}%",
                ))
        
        return signals
    
    def _check_profit_quality(self, ratios: Dict[str, Any]) -> List[Signal]:
        """Check if profits are backed by cash."""
        signals = []
        
        cfo_to_profit = ratios.get('cfo_to_profit', {})
        profit = ratios.get('net_profit', {})
        cfo = ratios.get('cash_from_operations', {})
        
        if cfo_to_profit:
            for year, ratio in cfo_to_profit.items():
                # Skip structural break years
                if year in self.structural_break_years:
                    continue
                
                # Skip if profit is negative (ratio meaningless)
                if profit.get(year, 0) <= 0:
                    continue
                
                if ratio < 0.5:
                    severity = SignalSeverity.HIGH if ratio < 0.3 else SignalSeverity.MEDIUM
                    
                    evidence = [
                        create_statement_evidence('P&L', 'Net Profit', year, profit.get(year)),
                        create_statement_evidence('Cash Flow', 'CFO', year, cfo.get(year)),
                    ]
                    
                    signals.append(create_signal(
                        family=SignalFamily.PROFIT_QUALITY,
                        category=SignalCategory.MANIPULATION,
                        year=year,
                        severity=severity,
                        description=f"CFO is only {ratio*100:.1f}% of Net Profit - poor earnings quality",
                        evidence_refs=evidence,
                        pattern=FRAUD_PATTERNS['profit_quality_decline']['description'],
                        confidence=0.8,
                        anomaly_type='profit_quality_decline',
                    ))
        
        # Check for persistent divergence
        if profit and cfo:
            years = sorted(set(profit.keys()) & set(cfo.keys()))
            divergence_count = 0
            divergence_years = []
            
            for year in years[-5:]:  # Last 5 years
                p = profit.get(year, 0)
                c = cfo.get(year, 0)
                if p > 0 and c < p * 0.7:
                    divergence_count += 1
                    divergence_years.append(year)
            
            if divergence_count >= 3:
                evidence = [
                    create_statement_evidence('P&L', 'Net Profit', years[-1], profit.get(years[-1])),
                    create_statement_evidence('Cash Flow', 'CFO', years[-1], cfo.get(years[-1])),
                ]
                
                signals.append(create_signal(
                    family=SignalFamily.PROFIT_QUALITY,
                    category=SignalCategory.MANIPULATION,
                    year=years[-1],
                    severity=SignalSeverity.CRITICAL,
                    description=f"Profit quality concerns in {divergence_count} of last 5 years",
                    evidence_refs=evidence,
                    pattern='Persistent gap between reported profits and cash generation',
                    confidence=0.9,
                    anomaly_type='persistent_profit_quality_issue',
                    company_comparison=f"Issues in years: {', '.join(map(str, divergence_years))}",
                ))
        
        return signals
    
    def _check_receivables_spike(
        self,
        ratios: Dict[str, Any],
        sector: str
    ) -> List[Signal]:
        """Check for debtor days spike."""
        signals = []
        
        debtor_days = ratios.get('debtor_days', {})
        if not debtor_days:
            return signals
        
        max_days = self.thresholds.get_threshold(sector, 'debtor_days_max', 90)
        years = sorted(debtor_days.keys())
        
        for i in range(1, len(years)):
            year = years[i]
            
            if year in self.structural_break_years:
                continue
            
            curr = debtor_days.get(year, 0)
            prev = debtor_days.get(years[i-1], 0)
            
            # Spike detection
            if prev > 0 and curr > prev * 1.3:
                evidence = [
                    EvidenceRef(
                        ref_type=RefType.RATIO,
                        filing_year=year,
                        line_item='Debtor Days',
                        snippet=f"Debtor Days: {curr:.0f} (prev: {prev:.0f})",
                    ),
                ]
                
                signals.append(create_signal(
                    family=SignalFamily.RECEIVABLES_SPIKE,
                    category=SignalCategory.MANIPULATION,
                    year=year,
                    severity=SignalSeverity.MEDIUM,
                    description=f"Debtor days spiked from {prev:.0f} to {curr:.0f}",
                    evidence_refs=evidence,
                    pattern=FRAUD_PATTERNS['debtor_days_spike']['description'],
                    confidence=0.75,
                    anomaly_type='debtor_days_spike',
                    company_comparison=f"{((curr/prev)-1)*100:.0f}% YoY increase",
                ))
            
            # Above industry norm
            if max_days and curr > max_days:
                evidence = [
                    EvidenceRef(
                        ref_type=RefType.RATIO,
                        filing_year=year,
                        line_item='Debtor Days',
                        snippet=f"Debtor Days: {curr:.0f}",
                    ),
                ]
                
                signals.append(create_signal(
                    family=SignalFamily.RECEIVABLES_SPIKE,
                    category=SignalCategory.MANIPULATION,
                    year=year,
                    severity=SignalSeverity.LOW,
                    description=f"Debtor days {curr:.0f} exceeds industry norm of {max_days}",
                    evidence_refs=evidence,
                    pattern='Slower collections than industry average',
                    confidence=0.7,
                    anomaly_type='high_debtor_days',
                    peer_comparison=f"Industry norm: {max_days} days",
                ))
        
        return signals
    
    def _check_one_time_gain_dependence(
        self,
        data: Dict[str, Any],
        ratios: Dict[str, Any],
        sector: str
    ) -> List[Signal]:
        """
        Check for unusual dependence on Other Income / one-time gains.
        
        NOTE: This is a PROXY indicator. For real RPT analysis, use actual
        annual report note parsing.
        """
        signals = []
        
        pnl = data.get('pnl')
        if pnl is None:
            return signals
        
        other_income_col = next((c for c in pnl.columns if 'Other Income' in c), None)
        revenue_col = ratios.get('revenue_col')
        
        if not other_income_col or not revenue_col or revenue_col not in pnl.columns:
            return signals
        
        other_income = pnl[other_income_col].to_dict()
        revenue = pnl[revenue_col].to_dict()
        
        years = sorted(set(other_income.keys()) & set(revenue.keys()))
        
        if len(years) < 3:
            return signals
        
        for i in range(2, len(years)):
            year = years[i]
            
            # Skip structural break years
            if year in self.structural_break_years:
                continue
            
            base_year = years[i-2]
            
            oi_start = other_income.get(base_year, 0)
            oi_end = other_income.get(year, 0)
            rev_start = revenue.get(base_year, 0)
            rev_end = revenue.get(year, 0)
            
            if oi_start <= 0 or rev_start <= 0:
                continue
            
            oi_growth = (oi_end - oi_start) / oi_start * 100
            rev_growth = (rev_end - rev_start) / rev_start * 100
            
            # Flag if Other Income grew >100% faster than revenue
            if oi_growth > rev_growth + 100 and oi_growth > 50:
                oi_rev_ratio = oi_end / rev_end * 100 if rev_end > 0 else 0
                
                # Only flag if material (>10% of revenue)
                if oi_rev_ratio > 10:
                    evidence = [
                        create_statement_evidence('P&L', other_income_col, year, oi_end),
                        create_statement_evidence('P&L', revenue_col, year, rev_end),
                    ]
                    
                    signals.append(create_signal(
                        family=SignalFamily.ONE_TIME_GAIN,
                        category=SignalCategory.MANIPULATION,
                        year=year,
                        severity=SignalSeverity.MEDIUM,
                        description=f"Other Income grew {oi_growth:.0f}% vs Revenue {rev_growth:.0f}% - now {oi_rev_ratio:.1f}% of revenue",
                        evidence_refs=evidence,
                        pattern='Unusual Other Income growth may indicate related party transactions or one-time gains',
                        confidence=0.6,  # Lower confidence as this is a proxy
                        anomaly_type='unusual_other_income',
                        company_comparison=f"OI/Revenue ratio: {oi_rev_ratio:.1f}%",
                    ))
        
        return signals
