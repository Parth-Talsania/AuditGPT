"""
Bank-specific signal detection for AuditGPT.

Banks and NBFCs have different financial dynamics requiring specialized analysis:
- NPA (Non-Performing Assets) trends
- Provisioning adequacy
- Capital Adequacy Ratio (CAR)
- Net Interest Margin
- Profit collapse patterns

IMPORTANT: For banks, distinguish between:
- Manipulation signals: Hidden bad loans, understated provisions
- Stress signals: Genuine asset quality deterioration, capital pressure
"""

from typing import List, Dict, Any, Optional, Set
import numpy as np

from auditgpt.signals.base import (
    Signal, SignalFamily, SignalCategory, SignalSeverity, create_signal
)
from auditgpt.evidence.models import (
    EvidenceRef, RefType, create_statement_evidence, create_ratio_evidence
)
from auditgpt.config.thresholds import SectorThresholds


class BankSignalDetector:
    """
    Specialized signal detection for banks and NBFCs.
    
    Key differences from corporate analysis:
    - CFO analysis skipped (loans are cash outflows)
    - Focus on NPA/NNPA trends
    - Capital adequacy monitoring
    - Provisioning coverage analysis
    """
    
    def __init__(self, thresholds: Optional[SectorThresholds] = None):
        self.thresholds = thresholds or SectorThresholds()
        self.structural_break_years: Set[int] = set()
    
    def set_structural_breaks(self, years: Set[int]):
        """Set years that are structural breaks (mergers/acquisitions)."""
        self.structural_break_years = years
    
    def detect_all(
        self,
        data: Dict[str, Any],
        ratios: Dict[str, Any],
        sector: str = 'BANK'
    ) -> List[Signal]:
        """
        Run all bank-specific signal detectors.
        
        Args:
            data: Company financial data dict
            ratios: Calculated financial ratios
            sector: Should be 'BANK' or 'NBFC'
            
        Returns:
            List of detected bank-specific signals
        """
        if sector not in ('BANK', 'NBFC', 'FINANCE'):
            return []
        
        signals = []
        
        # Asset quality signals (STRESS)
        signals.extend(self._check_npa_stress(data, ratios, sector))
        
        # Capital adequacy (STRESS)
        signals.extend(self._check_capital_adequacy(data, ratios, sector))
        
        # Profit collapse for banks (STRESS primarily)
        signals.extend(self._check_bank_profit_collapse(data, sector))
        
        # Margin compression (STRESS)
        signals.extend(self._check_margin_compression(data, sector))
        
        return signals
    
    def _check_npa_stress(
        self,
        data: Dict[str, Any],
        ratios: Dict[str, Any],
        sector: str
    ) -> List[Signal]:
        """
        Check NPA (Non-Performing Assets) stress.
        
        Looks for:
        - GNPA spikes (>50% YoY) - CRITICAL
        - GNPA consistently above industry norm (>7.5%) - HIGH
        - NNPA spikes indicating inadequate provisioning
        """
        signals = []
        
        max_npa = self.thresholds.get_threshold(sector, 'npa_max', 5.0)
        max_nnpa = self.thresholds.get_threshold(sector, 'nnpa_max', 3.0)
        
        # Try multiple sources for GNPA data
        gnpa_data = self._extract_gnpa_data(data, ratios)
        nnpa_data = self._extract_nnpa_data(data, ratios)
        
        # Check GNPA
        if gnpa_data:
            years = sorted(gnpa_data.keys())
            
            for i in range(1, len(years)):
                year = years[i]
                
                if year in self.structural_break_years:
                    continue
                
                curr = gnpa_data.get(year, 0)
                prev = gnpa_data.get(years[i-1], 0)
                
                # Skip if values are None or NaN
                if curr is None or prev is None:
                    continue
                if isinstance(curr, float) and np.isnan(curr):
                    continue
                if isinstance(prev, float) and np.isnan(prev):
                    continue
                
                # GNPA spike detection (>50% YoY) - CRITICAL
                if prev > 0 and curr > prev * 1.5:
                    evidence = [
                        create_ratio_evidence('Gross NPA %', years[i-1], prev),
                        create_ratio_evidence('Gross NPA %', year, curr),
                    ]
                    
                    signals.append(create_signal(
                        family=SignalFamily.ASSET_QUALITY,
                        category=SignalCategory.STRESS,
                        year=year,
                        severity=SignalSeverity.CRITICAL,
                        description=f"Gross NPA spiked by {((curr/prev)-1)*100:.1f}% to {curr:.2f}%",
                        evidence_refs=evidence,
                        pattern='Rapid deterioration of asset quality - potential hidden bad loans',
                        confidence=0.9,
                        anomaly_type='npa_spike',
                        company_comparison=f"YoY spike: {((curr/prev)-1)*100:.0f}%",
                        peer_comparison=f"Industry norm: {max_npa}%",
                    ))
                
                # Severely above norm (>1.5x industry norm) - HIGH
                elif curr > max_npa * 1.5:
                    evidence = [create_ratio_evidence('Gross NPA %', year, curr)]
                    
                    signals.append(create_signal(
                        family=SignalFamily.ASSET_QUALITY,
                        category=SignalCategory.STRESS,
                        year=year,
                        severity=SignalSeverity.HIGH,
                        description=f"Gross NPA at {curr:.2f}% is severely above industry norm ({max_npa}%)",
                        evidence_refs=evidence,
                        pattern='Sustained toxic asset burden - requires provisioning scrutiny',
                        confidence=0.85,
                        anomaly_type='high_npa_baseline',
                        peer_comparison=f"Industry norm: {max_npa}%, Current is {curr/max_npa:.1f}x norm",
                    ))
                
                # Elevated above norm - MEDIUM
                elif curr > max_npa:
                    evidence = [create_ratio_evidence('Gross NPA %', year, curr)]
                    
                    signals.append(create_signal(
                        family=SignalFamily.ASSET_QUALITY,
                        category=SignalCategory.STRESS,
                        year=year,
                        severity=SignalSeverity.MEDIUM,
                        description=f"Gross NPA at {curr:.2f}% exceeds industry norm of {max_npa}%",
                        evidence_refs=evidence,
                        pattern='Asset quality stress - monitor provisioning adequacy',
                        confidence=0.8,
                        anomaly_type='elevated_npa',
                        peer_comparison=f"Industry norm: {max_npa}%",
                    ))
        
        # Check NNPA (indicates provisioning adequacy)
        if nnpa_data:
            years = sorted(nnpa_data.keys())
            
            for i in range(1, len(years)):
                year = years[i]
                
                if year in self.structural_break_years:
                    continue
                
                curr = nnpa_data.get(year, 0)
                prev = nnpa_data.get(years[i-1], 0)
                
                if curr is None or prev is None:
                    continue
                if isinstance(curr, float) and np.isnan(curr):
                    continue
                
                # NNPA spike AND >3% (provisioning may be inadequate)
                if prev > 0 and curr > prev * 1.5 and curr > 3:
                    evidence = [
                        create_ratio_evidence('Net NPA %', years[i-1], prev),
                        create_ratio_evidence('Net NPA %', year, curr),
                    ]
                    
                    signals.append(create_signal(
                        family=SignalFamily.PROVISIONING,
                        category=SignalCategory.STRESS,
                        year=year,
                        severity=SignalSeverity.CRITICAL,
                        description=f"Net NPA spiked to {curr:.2f}% - provisioning may be inadequate",
                        evidence_refs=evidence,
                        pattern='Net NPA spike indicates insufficient provision coverage',
                        confidence=0.9,
                        anomaly_type='nnpa_spike',
                        company_comparison=f"YoY increase: {((curr/prev)-1)*100:.0f}%",
                    ))
        
        return signals
    
    def _extract_gnpa_data(self, data: Dict[str, Any], ratios: Dict[str, Any]) -> Optional[Dict]:
        """Extract GNPA data from multiple sources."""
        # Try ratios dict first (from engine)
        if ratios and 'gnpa' in ratios:
            gnpa_list = ratios['gnpa']
            years = ratios.get('years', [])
            if gnpa_list and years and len(gnpa_list) == len(years):
                return {y: v for y, v in zip(years, gnpa_list) if v is not None}
        
        # Try ratios DataFrame
        ratios_df = data.get('ratios')
        if ratios_df is not None:
            gnpa_col = next(
                (c for c in ratios_df.columns if any(x in c for x in ['Gross NPA', 'GNPA', 'Gross Non'])),
                None
            )
            if gnpa_col:
                return ratios_df[gnpa_col].to_dict()
        
        # Try P&L DataFrame (some banks report GNPA there)
        pnl = data.get('pnl')
        if pnl is not None:
            gnpa_col = next(
                (c for c in pnl.columns if any(x in c for x in ['Gross NPA', 'GNPA %'])),
                None
            )
            if gnpa_col:
                return pnl[gnpa_col].to_dict()
        
        return None
    
    def _extract_nnpa_data(self, data: Dict[str, Any], ratios: Dict[str, Any]) -> Optional[Dict]:
        """Extract NNPA data from multiple sources."""
        # Try ratios dict first
        if ratios and 'nnpa' in ratios:
            nnpa_list = ratios['nnpa']
            years = ratios.get('years', [])
            if nnpa_list and years and len(nnpa_list) == len(years):
                return {y: v for y, v in zip(years, nnpa_list) if v is not None}
        
        # Try ratios DataFrame
        ratios_df = data.get('ratios')
        if ratios_df is not None:
            nnpa_col = next(
                (c for c in ratios_df.columns if any(x in c for x in ['Net NPA', 'NNPA', 'Net Non'])),
                None
            )
            if nnpa_col:
                return ratios_df[nnpa_col].to_dict()
        
        return None
    
    def _check_capital_adequacy(
        self,
        data: Dict[str, Any],
        ratios: Dict[str, Any],
        sector: str
    ) -> List[Signal]:
        """Check Capital Adequacy Ratio (CAR/CRAR)."""
        signals = []
        
        ratios_df = data.get('ratios')
        if ratios_df is None:
            return signals
        
        min_car = self.thresholds.get_threshold(sector, 'car_min', 12)
        
        # Find CAR column
        car_col = next(
            (c for c in ratios_df.columns if any(x in c for x in ['Capital Adequacy', 'CAR', 'CRAR'])),
            None
        )
        
        if not car_col:
            return signals
        
        car = ratios_df[car_col].to_dict()
        years = sorted(car.keys())
        
        for year in years:
            if year in self.structural_break_years:
                continue
            
            curr_car = car.get(year, 0)
            
            if curr_car > 0 and curr_car < min_car:
                severity = SignalSeverity.CRITICAL if curr_car < 9 else SignalSeverity.HIGH
                
                evidence = [create_ratio_evidence(car_col, year, curr_car)]
                
                signals.append(create_signal(
                    family=SignalFamily.CAPITAL_ADEQUACY,
                    category=SignalCategory.STRESS,
                    year=year,
                    severity=severity,
                    description=f"Capital Adequacy Ratio at {curr_car:.1f}% below regulatory minimum ({min_car}%)",
                    evidence_refs=evidence,
                    pattern='Insufficient capital buffer - bank may need capital infusion',
                    confidence=0.95,
                    anomaly_type='low_capital_adequacy',
                    peer_comparison=f"Regulatory minimum: {min_car}%",
                ))
        
        return signals
    
    def _check_bank_profit_collapse(
        self,
        data: Dict[str, Any],
        sector: str
    ) -> List[Signal]:
        """
        Check for bank profit collapse.
        
        FIX: Deduplicate bank_loss and bank_profit_collapse for same year.
        """
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
        
        # Track flagged years to avoid duplicates
        flagged_years = set()
        
        for i in range(1, len(years)):
            year = years[i]
            
            if year in self.structural_break_years:
                continue
            
            if year in flagged_years:
                continue
            
            curr = net_profit.get(year, 0)
            prev = net_profit.get(years[i-1], 0)
            
            # Loss after profit - this is the primary signal
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
                    description=f"Bank reported loss of Rs.{abs(curr):,.0f} Cr after profit of Rs.{prev:,.0f} Cr",
                    evidence_refs=evidence,
                    pattern='Bank turned loss-making - serious asset quality or provisioning issues',
                    confidence=0.95,
                    anomaly_type='bank_loss',
                    company_comparison=f"Swing: Rs.{prev + abs(curr):,.0f} Cr",
                ))
                flagged_years.add(year)
            
            # Profit collapse (>50% drop but not to loss) - only if not already flagged
            elif prev > 0 and curr > 0 and curr < prev * 0.5:
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
                    pattern='Sudden profit collapse - potential asset quality issues or provisioning spike',
                    confidence=0.85,
                    anomaly_type='bank_profit_collapse',
                ))
                flagged_years.add(year)
        
        return signals
    
    def _check_margin_compression(
        self,
        data: Dict[str, Any],
        sector: str
    ) -> List[Signal]:
        """Check Operating Profit Margin compression for banks."""
        signals = []
        
        pnl = data.get('pnl')
        if pnl is None:
            return signals
        
        if 'OPM %' not in pnl.columns:
            return signals
        
        opm = pnl['OPM %'].to_dict()
        years = sorted(opm.keys())
        
        if len(years) < 4:
            return signals
        
        # Compare recent 3 years vs historical
        recent_opm = [opm.get(y, 0) for y in years[-3:]]
        historical_opm = [opm.get(y, 0) for y in years[:-3]]
        
        if not historical_opm or np.mean(historical_opm) <= 0:
            return signals
        
        recent_avg = np.mean(recent_opm)
        historical_avg = np.mean(historical_opm)
        
        if recent_avg < historical_avg * 0.7:
            evidence = [
                create_ratio_evidence('OPM %', years[-3], opm.get(years[-3])),
                create_ratio_evidence('OPM %', years[-1], opm.get(years[-1])),
            ]
            
            signals.append(create_signal(
                family=SignalFamily.PROFITABILITY_COLLAPSE,
                category=SignalCategory.STRESS,
                year=years[-1],
                severity=SignalSeverity.MEDIUM,
                description=f"Operating margin compressed from {historical_avg:.1f}% to {recent_avg:.1f}%",
                evidence_refs=evidence,
                pattern='Declining margins may indicate rising funding costs or competitive pressure',
                confidence=0.75,
                anomaly_type='bank_margin_compression',
                company_comparison=f"Margin decline: {((historical_avg-recent_avg)/historical_avg)*100:.0f}%",
            ))
        
        return signals
