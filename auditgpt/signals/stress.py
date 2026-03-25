"""
Financial stress signal detection for AuditGPT.

Detects signals that indicate financial stress or asset quality issues:
- Leverage stress
- Interest coverage deterioration
- Liquidity pressure
- Profitability collapse
- Weak CFO generation
- ROCE decline
"""

from typing import List, Dict, Any, Optional
import numpy as np

from auditgpt.signals.base import (
    Signal, SignalFamily, SignalCategory, SignalSeverity, create_signal
)
from auditgpt.evidence.models import EvidenceRef, RefType, create_statement_evidence, create_ratio_evidence
from auditgpt.config.constants import FRAUD_PATTERNS
from auditgpt.config.thresholds import SectorThresholds


class StressSignalDetector:
    """
    Detects financial stress signals in financial data.
    
    These signals indicate genuine business stress rather than manipulation.
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
        Run all stress signal detectors.
        
        Args:
            data: Company financial data dict
            ratios: Calculated financial ratios
            sector: Company sector code
            
        Returns:
            List of detected stress signals
        """
        signals = []
        
        # Leverage analysis (skip for banks - different leverage norms)
        if not self.thresholds.is_banking_sector(sector):
            signals.extend(self._check_leverage_stress(ratios, sector))
            signals.extend(self._check_debt_explosion(ratios, sector))
        
        # Working capital (skip for banks)
        if not self.thresholds.is_banking_sector(sector):
            signals.extend(self._check_working_capital(ratios, sector))
        
        # ROCE decline (all sectors)
        signals.extend(self._check_roce_decline(ratios, sector))
        
        # Profitability collapse (all sectors)
        signals.extend(self._check_profitability_collapse(data, sector))
        
        # Weak CFO (skip for banks)
        if not self.thresholds.should_skip_cfo_analysis(sector):
            signals.extend(self._check_weak_cfo(ratios))
        
        return signals
    
    def _check_leverage_stress(
        self,
        ratios: Dict[str, Any],
        sector: str
    ) -> List[Signal]:
        """Check for excessive leverage."""
        signals = []
        
        debt_equity = ratios.get('debt_equity', {})
        if not debt_equity:
            return signals
        
        max_de = self.thresholds.get_threshold(sector, 'debt_equity_max', 1.5)
        multiplier = self.thresholds.get_peer_comparison_multiplier(sector, 'debt_equity_max')
        
        for year, de in debt_equity.items():
            if year in self.structural_break_years:
                continue
            
            if de > max_de * multiplier:
                severity = SignalSeverity.HIGH if de > max_de * 2 else SignalSeverity.MEDIUM
                
                evidence = [
                    create_ratio_evidence('Debt/Equity', year, de),
                ]
                
                signals.append(create_signal(
                    family=SignalFamily.LEVERAGE_STRESS,
                    category=SignalCategory.STRESS,
                    year=year,
                    severity=severity,
                    description=f"Debt/Equity ratio {de:.2f} exceeds industry norm of {max_de}",
                    evidence_refs=evidence,
                    pattern='Excessive leverage for industry',
                    confidence=0.85,
                    anomaly_type='high_leverage',
                    peer_comparison=f"Industry norm: {max_de}",
                ))
        
        return signals
    
    def _check_debt_explosion(
        self,
        ratios: Dict[str, Any],
        sector: str
    ) -> List[Signal]:
        """Check for explosive debt growth with materiality thresholds."""
        signals = []
        
        debt = ratios.get('total_debt', {})
        revenue = ratios.get('revenue', {})
        
        if not debt or not revenue:
            return signals
        
        years = sorted(debt.keys())
        
        for i in range(1, len(years)):
            year = years[i]
            
            if year in self.structural_break_years:
                continue
            
            curr_debt = debt.get(year, 0)
            prev_debt = debt.get(years[i-1], 0)
            curr_revenue = revenue.get(year, 1)
            
            # MATERIALITY CHECK: Only flag if debt is significant
            debt_to_revenue = curr_debt / curr_revenue if curr_revenue > 0 else 0
            debt_increase = curr_debt - prev_debt
            
            # Skip if previous debt was immaterial (<1% of revenue)
            if prev_debt > 0 and prev_debt < curr_revenue * 0.01:
                continue
            
            # Check for >50% debt increase
            if prev_debt > 0 and curr_debt > prev_debt * 1.5:
                # Only flag if debt is material (>5% of revenue)
                if debt_to_revenue > 0.05 and debt_increase > curr_revenue * 0.03:
                    severity = SignalSeverity.HIGH if curr_debt > prev_debt * 2 else SignalSeverity.MEDIUM
                    
                    evidence = [
                        create_statement_evidence('Balance Sheet', 'Borrowings', years[i-1], prev_debt),
                        create_statement_evidence('Balance Sheet', 'Borrowings', year, curr_debt),
                    ]
                    
                    signals.append(create_signal(
                        family=SignalFamily.LEVERAGE_STRESS,
                        category=SignalCategory.STRESS,
                        year=year,
                        severity=severity,
                        description=f"Debt increased by {((curr_debt/prev_debt)-1)*100:.1f}% (now {debt_to_revenue*100:.1f}% of revenue)",
                        evidence_refs=evidence,
                        pattern=FRAUD_PATTERNS['debt_explosion']['description'],
                        confidence=0.8,
                        anomaly_type='debt_explosion',
                        company_comparison=f"YoY increase: {((curr_debt/prev_debt)-1)*100:.0f}%",
                    ))
        
        return signals
    
    def _check_working_capital(
        self,
        ratios: Dict[str, Any],
        sector: str
    ) -> List[Signal]:
        """Check working capital deterioration."""
        signals = []
        
        wc_days = ratios.get('working_capital_days', {})
        if not wc_days:
            return signals
        
        years = sorted(wc_days.keys())
        if len(years) < 3:
            return signals
        
        first_val = wc_days.get(years[0], 0)
        last_val = wc_days.get(years[-1], 0)
        
        if first_val > 0 and last_val > first_val * 1.4:
            evidence = [
                create_ratio_evidence('Working Capital Days', years[0], first_val),
                create_ratio_evidence('Working Capital Days', years[-1], last_val),
            ]
            
            signals.append(create_signal(
                family=SignalFamily.LIQUIDITY_PRESSURE,
                category=SignalCategory.STRESS,
                year=years[-1],
                severity=SignalSeverity.MEDIUM,
                description=f"Working capital days increased from {first_val:.0f} to {last_val:.0f}",
                evidence_refs=evidence,
                pattern=FRAUD_PATTERNS['working_capital_deterioration']['description'],
                confidence=0.75,
                anomaly_type='working_capital_deterioration',
                company_comparison=f"{((last_val/first_val)-1)*100:.0f}% increase over period",
            ))
        
        return signals
    
    def _check_roce_decline(
        self,
        ratios: Dict[str, Any],
        sector: str
    ) -> List[Signal]:
        """Check for consistent ROCE decline."""
        signals = []
        
        roce = ratios.get('roce_', {})
        if not roce:
            return signals
        
        min_roce = self.thresholds.get_threshold(sector, 'roce_min', 12)
        years = sorted(roce.keys())
        
        if len(years) < 3:
            return signals
        
        # Check for consistent decline
        declining_years = 0
        for i in range(1, len(years)):
            if roce.get(years[i], 0) < roce.get(years[i-1], 0):
                declining_years += 1
        
        if declining_years >= len(years) - 2:  # Most years declining
            evidence = [
                create_ratio_evidence('ROCE %', years[0], roce.get(years[0])),
                create_ratio_evidence('ROCE %', years[-1], roce.get(years[-1])),
            ]
            
            signals.append(create_signal(
                family=SignalFamily.ROCE_DECLINE,
                category=SignalCategory.STRESS,
                year=years[-1],
                severity=SignalSeverity.MEDIUM,
                description=f"ROCE has declined in {declining_years} of {len(years)-1} years",
                evidence_refs=evidence,
                pattern=FRAUD_PATTERNS['roce_decline']['description'],
                confidence=0.8,
                anomaly_type='roce_decline',
                company_comparison=f"Declining {declining_years}/{len(years)-1} years",
            ))
        
        # Check against industry norm
        last_roce = roce.get(years[-1], 0)
        if min_roce and last_roce < min_roce:
            evidence = [
                create_ratio_evidence('ROCE %', years[-1], last_roce),
            ]
            
            signals.append(create_signal(
                family=SignalFamily.ROCE_DECLINE,
                category=SignalCategory.STRESS,
                year=years[-1],
                severity=SignalSeverity.LOW,
                description=f"ROCE {last_roce:.1f}% below industry minimum of {min_roce}%",
                evidence_refs=evidence,
                pattern='Below industry average return on capital',
                confidence=0.75,
                anomaly_type='low_roce',
                peer_comparison=f"Industry minimum: {min_roce}%",
            ))
        
        return signals
    
    def _check_profitability_collapse(
        self,
        data: Dict[str, Any],
        sector: str
    ) -> List[Signal]:
        """Check for profitability collapse."""
        signals = []
        
        pnl = data.get('pnl')
        if pnl is None:
            return signals
        
        # Find net profit column
        np_col = None
        for col in ['Net Profit', 'Net Profit+']:
            if col in pnl.columns:
                np_col = col
                break
        
        if not np_col:
            return signals
        
        net_profit = pnl[np_col].to_dict()
        years = sorted(net_profit.keys())
        
        # Track if we've already flagged a year to avoid duplicates
        flagged_years = set()
        
        for i in range(1, len(years)):
            year = years[i]
            
            if year in self.structural_break_years:
                continue
            
            curr = net_profit.get(year, 0)
            prev = net_profit.get(years[i-1], 0)
            
            # FIX: Avoid duplicate signals for same year
            if year in flagged_years:
                continue
            
            # Check for loss after profit
            if curr < 0 and prev > 0:
                evidence = [
                    create_statement_evidence('P&L', np_col, years[i-1], prev),
                    create_statement_evidence('P&L', np_col, year, curr),
                ]
                
                signals.append(create_signal(
                    family=SignalFamily.PROFITABILITY_COLLAPSE,
                    category=SignalCategory.STRESS,
                    year=year,
                    severity=SignalSeverity.CRITICAL,
                    description=f"Net profit collapsed to loss of Rs.{abs(curr):,.0f} Cr from profit of Rs.{prev:,.0f} Cr",
                    evidence_refs=evidence,
                    pattern='Profitability collapse - investigate underlying causes',
                    confidence=0.95,
                    anomaly_type='profitability_collapse',
                    company_comparison=f"Swing: Rs.{prev + abs(curr):,.0f} Cr",
                ))
                flagged_years.add(year)
            
            # Check for >50% profit decline (but not to loss)
            elif prev > 0 and curr >= 0 and curr < prev * 0.5:
                evidence = [
                    create_statement_evidence('P&L', np_col, years[i-1], prev),
                    create_statement_evidence('P&L', np_col, year, curr),
                ]
                
                signals.append(create_signal(
                    family=SignalFamily.PROFITABILITY_COLLAPSE,
                    category=SignalCategory.STRESS,
                    year=year,
                    severity=SignalSeverity.HIGH,
                    description=f"Net profit dropped {((prev-curr)/prev)*100:.1f}% from Rs.{prev:,.0f} Cr to Rs.{curr:,.0f} Cr",
                    evidence_refs=evidence,
                    pattern='Significant profit decline',
                    confidence=0.85,
                    anomaly_type='profit_decline',
                    company_comparison=f"YoY decline: {((prev-curr)/prev)*100:.0f}%",
                ))
                flagged_years.add(year)
        
        return signals
    
    def _check_weak_cfo(self, ratios: Dict[str, Any]) -> List[Signal]:
        """Check for persistently weak/negative CFO."""
        signals = []
        
        cfo = ratios.get('cash_from_operations', {})
        if not cfo:
            return signals
        
        years = sorted(cfo.keys())
        if len(years) < 3:
            return signals
        
        # Count consecutive negative CFO years
        consecutive_negative = 0
        negative_streak_start = None
        
        for i, year in enumerate(years):
            if cfo.get(year, 0) < 0:
                if consecutive_negative == 0:
                    negative_streak_start = year
                consecutive_negative += 1
            else:
                consecutive_negative = 0
                negative_streak_start = None
        
        if consecutive_negative >= 2 and negative_streak_start:
            evidence = [
                create_statement_evidence('Cash Flow', 'CFO', years[-1], cfo.get(years[-1])),
            ]
            
            signals.append(create_signal(
                family=SignalFamily.WEAK_CFO,
                category=SignalCategory.STRESS,
                year=years[-1],
                severity=SignalSeverity.HIGH if consecutive_negative >= 3 else SignalSeverity.MEDIUM,
                description=f"Negative operating cash flow for {consecutive_negative} consecutive years",
                evidence_refs=evidence,
                pattern='Persistently negative cash generation from operations',
                confidence=0.85,
                anomaly_type='weak_cfo_generation',
                company_comparison=f"Negative CFO since FY{negative_streak_start}",
            ))
        
        return signals
