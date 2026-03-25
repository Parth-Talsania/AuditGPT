"""
Report section generators for AuditGPT.

Required sections:
1. Executive Summary
2. Manipulation/Fraud-Risk Signals
3. Financial-Stress/Asset-Quality Signals
4. Red-Flag Timeline
5. Auditor Note Trend
6. Related-Party Trend
7. Peer Selection Explanation
8. Peer Comparison Table
9. Uncertainty/Missing-Data Disclosures
"""

from typing import List, Dict, Any, Optional
from datetime import datetime

from auditgpt.signals.base import Signal, SignalSeverity, SignalCategory
from auditgpt.scoring.dual_scorer import DualScore
from auditgpt.evidence.models import SentimentTrend, EvidenceRef

# Import XAI engine for AI-powered summaries
try:
    from auditgpt.ai.xai_engine import ExplainableAIEngine
    xai_engine = ExplainableAIEngine()
except ImportError:
    xai_engine = None


class ReportSectionGenerator:
    """
    Generates individual report sections.
    
    Each section includes proper evidence citations where available.
    Explicitly states "data unavailable" when information is missing.
    """
    
    # Severity icons
    SEVERITY_ICONS = {
        'CRITICAL': '🔴',
        'HIGH': '🟠',
        'MEDIUM': '🟡',
        'LOW': '🟢',
        'INFO': '🟦',
    }
    
    # Risk level icons
    RISK_ICONS = {
        'CRITICAL': '🔴',
        'HIGH': '🟠',
        'MEDIUM': '🟡',
        'LOW': '🟢',
    }
    
    def generate_header(
        self,
        company_data: Dict[str, Any],
    ) -> str:
        """Generate report header."""
        lines = [
            "=" * 70,
            "              AUDITGPT FORENSIC ANALYSIS REPORT",
            "           (Hybrid Deterministic + AI Forensic Engine)",
            "=" * 70,
            "",
            f"Company: {company_data.get('name', company_data.get('ticker', 'Unknown'))}",
            f"Ticker: {company_data.get('ticker', 'N/A')}",
            f"Sector: {company_data.get('sector', 'Unknown')}",
            f"Analysis Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        ]
        return "\n".join(lines)
    
    def generate_executive_summary(
        self,
        dual_score: DualScore,
        signals: List[Signal],
        sector: str,
        company: str = "Company",
    ) -> str:
        """
        Generate executive summary with dual scores.
        
        Uses XAI engine for intelligent reasoning if available.
        """
        lines = [
            "",
            "-" * 70,
            "                         EXECUTIVE SUMMARY",
            "-" * 70,
            "",
        ]
        
        # Dual Score Display
        manip_icon = self.RISK_ICONS.get(dual_score.manipulation_level, '⚪')
        stress_icon = self.RISK_ICONS.get(dual_score.stress_level, '⚪')
        combined_icon = self.RISK_ICONS.get(dual_score.combined_level, '⚪')
        
        lines.append("FORENSIC RISK SCORES:")
        lines.append(f"  {manip_icon} Manipulation/Fraud Risk: {dual_score.manipulation_score}/100 ({dual_score.manipulation_level})")
        lines.append(f"  {stress_icon} Financial Stress Risk:   {dual_score.stress_score}/100 ({dual_score.stress_level})")
        lines.append(f"  {combined_icon} Combined Forensic Score: {dual_score.combined_score}/100 ({dual_score.combined_level})")
        lines.append("")
        
        # Try XAI-powered reasoning first
        xai_reasoning = None
        if xai_engine is not None:
            try:
                # Convert signals to dict format for XAI
                # Use description field (explanation_seed may be empty)
                signal_dicts = [
                    {
                        'severity': s.current_severity.value if hasattr(s.current_severity, 'value') else str(s.current_severity),
                        'description': s.description or s.explanation_seed or str(s),
                        'category': s.manipulation_or_stress.value if hasattr(s.manipulation_or_stress, 'value') else 'UNKNOWN',
                    }
                    for s in signals[:10]
                ]
                
                dual_score_dict = {
                    'manipulation_score': dual_score.manipulation_score,
                    'manipulation_level': dual_score.manipulation_level,
                    'stress_score': dual_score.stress_score,
                    'stress_level': dual_score.stress_level,
                    'combined_score': dual_score.combined_score,
                    'combined_level': dual_score.combined_level,
                }
                
                xai_reasoning = xai_engine.generate_executive_summary(
                    company=company,
                    sector=sector,
                    dual_score=dual_score_dict,
                    signals=signal_dicts,
                )
            except Exception as e:
                xai_reasoning = None
        
        # Fall back to template-based reasoning
        if not xai_reasoning:
            xai_reasoning = self._generate_specific_reasoning(signals, sector)
        
        # Display reasoning based on risk level
        if dual_score.combined_level == 'CRITICAL':
            lines.append("ALERT: CRITICAL RISK DETECTED")
            if xai_reasoning:
                lines.append(f"  {xai_reasoning}")
            else:
                lines.append("  Multiple severe red flags requiring immediate investigation.")
        elif dual_score.combined_level == 'HIGH':
            lines.append("WARNING: HIGH RISK")
            if xai_reasoning:
                lines.append(f"  {xai_reasoning}")
        elif dual_score.combined_level == 'MEDIUM':
            lines.append("CAUTION: MODERATE RISK")
            if xai_reasoning:
                lines.append(f"  {xai_reasoning}")
            else:
                lines.append("  Some concerns identified. Continued monitoring recommended.")
        else:
            lines.append("STATUS: LOW RISK")
            if xai_reasoning:
                lines.append(f"  {xai_reasoning}")
            else:
                lines.append("  Financial patterns appear healthy. No major red flags detected.")
        
        # Signal counts
        lines.append("")
        lines.append("Signal Summary:")
        lines.append(f"  Manipulation Signals: {dual_score.manipulation_signal_count} ({dual_score.manipulation_critical_count} critical)")
        lines.append(f"  Stress Signals: {dual_score.stress_signal_count} ({dual_score.stress_critical_count} critical)")
        
        return "\n".join(lines)
    
    def generate_manipulation_signals_section(
        self,
        signals: List[Signal],
    ) -> str:
        """Generate manipulation/fraud-risk signals section."""
        manipulation_signals = [
            s for s in signals
            if s.is_manipulation_signal and s.current_severity != SignalSeverity.INFO
        ]
        
        lines = [
            "",
            "-" * 70,
            "              MANIPULATION / FRAUD-RISK SIGNALS",
            "-" * 70,
            "",
        ]
        
        if not manipulation_signals:
            lines.append("No manipulation signals detected.")
            return "\n".join(lines)
        
        # Group by year
        by_year = self._group_signals_by_year(manipulation_signals)
        
        for year in sorted(by_year.keys(), reverse=True):
            year_signals = by_year[year]
            lines.append(f"FY{year}:")
            
            for signal in year_signals:
                icon = self.SEVERITY_ICONS.get(signal.current_severity.value, '⚪')
                lines.append(f"  {icon} [{signal.current_severity.value}] {signal.description}")
                
                if signal.pattern:
                    lines.append(f"      Pattern: {signal.pattern}")
                
                # Evidence citation
                if signal.evidence_refs:
                    lines.append(f"      Evidence: {signal.primary_citation}")
                    if signal.confidence < 0.7:
                        lines.append(f"      Confidence: {signal.confidence*100:.0f}% (reduced due to data limitations)")
            
            lines.append("")
        
        return "\n".join(lines)
    
    def generate_stress_signals_section(
        self,
        signals: List[Signal],
    ) -> str:
        """Generate financial-stress/asset-quality signals section."""
        stress_signals = [
            s for s in signals
            if s.is_stress_signal and s.current_severity != SignalSeverity.INFO
        ]
        
        lines = [
            "",
            "-" * 70,
            "           FINANCIAL-STRESS / ASSET-QUALITY SIGNALS",
            "-" * 70,
            "",
        ]
        
        if not stress_signals:
            lines.append("No financial stress signals detected.")
            return "\n".join(lines)
        
        by_year = self._group_signals_by_year(stress_signals)
        
        for year in sorted(by_year.keys(), reverse=True):
            year_signals = by_year[year]
            lines.append(f"FY{year}:")
            
            for signal in year_signals:
                icon = self.SEVERITY_ICONS.get(signal.current_severity.value, '⚪')
                lines.append(f"  {icon} [{signal.current_severity.value}] {signal.description}")
                
                if signal.pattern:
                    lines.append(f"      Pattern: {signal.pattern}")
                
                if signal.evidence_refs:
                    lines.append(f"      Evidence: {signal.primary_citation}")
            
            lines.append("")
        
        return "\n".join(lines)
    
    def generate_red_flag_timeline(
        self,
        signals: List[Signal],
    ) -> str:
        """Generate red-flag timeline with source references."""
        # Exclude INFO signals
        significant_signals = [s for s in signals if s.current_severity != SignalSeverity.INFO]
        
        lines = [
            "",
            "-" * 70,
            "              RED FLAG TIMELINE (WITH SOURCE REFERENCES)",
            "-" * 70,
            "",
            "(Each flag includes: Year, Statement Type, and Exact Source Reference)",
            "",
        ]
        
        if not significant_signals:
            lines.append("No red flags detected in the analysis period.")
            return "\n".join(lines)
        
        by_year = self._group_signals_by_year(significant_signals)
        
        for year in sorted(by_year.keys()):
            lines.append(f"FY{year}:")
            
            for signal in by_year[year]:
                icon = self.SEVERITY_ICONS.get(signal.current_severity.value, '⚪')
                category = "M" if signal.is_manipulation_signal else "S"
                
                lines.append(f"  {icon} [{signal.current_severity.value}][{category}] {signal.description}")
                
                # Statement type and source reference
                stmt_type = signal._get_statement_type()
                lines.append(f"      Statement: {stmt_type}")
                lines.append(f"      Source: {signal.primary_citation}")
            
            lines.append("")
        
        return "\n".join(lines)
    
    def generate_auditor_sentiment_section(
        self,
        sentiment_trend: Optional[SentimentTrend],
        has_real_notes: bool = False,
    ) -> str:
        """
        Generate auditor note sentiment trend section.
        
        IMPORTANT: If real notes unavailable, explicitly states this.
        """
        lines = [
            "",
            "-" * 70,
            "              AUDITOR NOTE SENTIMENT ANALYSIS",
            "-" * 70,
            "",
        ]
        
        if not sentiment_trend or not sentiment_trend.available:
            reason = sentiment_trend.reason if sentiment_trend else "No sentiment data available"
            lines.append(f"STATUS: {reason}")
            lines.append("")
            lines.append("NOTE: Full auditor note analysis requires annual report PDF parsing.")
            lines.append("      This analysis may be based on simulated/proxy data.")
            return "\n".join(lines)
        
        # Add disclaimer if not real notes
        if not has_real_notes:
            lines.append("DISCLAIMER: Auditor sentiment analysis based on proxy indicators.")
            lines.append("            Actual annual report notes were not parsed.")
            lines.append("")
        
        lines.append("Auditor Sentiment Trend:")
        
        sorted_years = sentiment_trend.get_sorted_years()
        category_icons = {
            'CRITICAL': '🔴',
            'CONCERNING': '🟠',
            'NEUTRAL': '🟡',
            'STABLE': '🟢',
        }
        
        for year in sorted_years:
            year_data = sentiment_trend.years[year]
            icon = category_icons.get(year_data.category, '⚪')
            
            lines.append(f"  {year}: {icon} [{year_data.category}] Score: {year_data.score}")
            
            if year_data.hedged_keywords_found:
                keywords = ', '.join(year_data.hedged_keywords_found[:3])
                lines.append(f"         Keywords: {keywords}")
        
        # Trend description
        lines.append("")
        lines.append(f"TREND: {sentiment_trend.get_trend_description()}")
        
        return "\n".join(lines)
    
    def generate_rpt_section(
        self,
        rpt_data: Optional[Dict[str, Any]],
        has_real_rpt_notes: bool = False,
        signals: Optional[List[Signal]] = None,
    ) -> str:
        """
        Generate related-party transaction section.
        
        IMPORTANT: Explicitly states if using proxy data (Other Income).
        """
        lines = [
            "",
            "-" * 70,
            "         RELATED PARTY TRANSACTION (RPT) ANALYSIS",
            "-" * 70,
            "",
        ]
        
        if has_real_rpt_notes:
            lines.append("SOURCE: Actual RPT note extraction from annual reports")
        else:
            lines.append("SOURCE: Proxy analysis using 'Other Income' trend")
            lines.append("NOTE: Actual RPT notes were not parsed. This is an indicative analysis only.")
        
        lines.append("")
        
        if not rpt_data:
            lines.append("No RPT/Other Income data available for analysis.")
            return "\n".join(lines)
        
        # Display the trend
        years = sorted(rpt_data.keys())[-10:]  # Last 10 years
        
        lines.append("Other Income vs Revenue Trend:")
        lines.append("")
        lines.append("   Year    Other Income    Revenue      OI/Rev %    Trend")
        lines.append("   " + "-" * 55)
        
        prev_ratio = None
        for year in years:
            data = rpt_data[year]
            oi = data.get('other_income', 0)
            rev = data.get('revenue', 0)
            ratio = data.get('oi_to_revenue_pct', 0)
            
            # Trend indicator
            if prev_ratio is not None:
                if ratio > prev_ratio + 2:
                    trend = '↑ UP'
                elif ratio < prev_ratio - 2:
                    trend = '↓ DOWN'
                else:
                    trend = '→ STABLE'
            else:
                trend = '-'
            
            lines.append(f"   {year}    Rs.{oi:>10,.0f}    Rs.{rev:>10,.0f}    {ratio:>6.1f}%    {trend}")
            prev_ratio = ratio
        
        # Show flagged RPT signals if any
        if signals:
            rpt_signals = [s for s in signals if s.signal_family.value == 'one_time_gain']
            if rpt_signals:
                lines.append("")
                lines.append("FLAGGED ANOMALIES:")
                for signal in rpt_signals:
                    lines.append(f"  - FY{signal.year_latest}: {signal.description}")
        
        return "\n".join(lines)
    
    def generate_peer_explanation_section(
        self,
        peer_selection_explanation: str,
        peers_used: List[str],
    ) -> str:
        """Generate peer selection explanation section."""
        lines = [
            "",
            "-" * 70,
            "                    PEER SELECTION EXPLANATION",
            "-" * 70,
            "",
        ]
        
        if not peers_used:
            lines.append("No peers available for comparison.")
            return "\n".join(lines)
        
        lines.append(peer_selection_explanation)
        
        return "\n".join(lines)
    
    def generate_peer_comparison_table(
        self,
        peer_comparison: Dict[str, Any],
    ) -> str:
        """Generate peer comparison table section."""
        lines = [
            "",
            "-" * 70,
            "                       PEER COMPARISON TABLE",
            "-" * 70,
            "",
        ]
        
        if not peer_comparison or not peer_comparison.get('peers'):
            lines.append("Peer comparison data not available.")
            return "\n".join(lines)
        
        lines.append(f"Peers: {', '.join(peer_comparison['peers'])}")
        lines.append("")
        
        comparisons = peer_comparison.get('comparisons', [])
        if not comparisons:
            lines.append("No metric comparisons available.")
            return "\n".join(lines)
        
        lines.append("Metric              Company     Peer Median  Position    Deviation")
        lines.append("-" * 65)
        
        for comp in comparisons:
            metric = comp.get('metric', 'Unknown')[:18].ljust(18)
            company_val = f"{comp.get('company_value', 0):.2f}".rjust(10)
            peer_avg = f"{comp.get('peer_average', 0):.2f}".rjust(12)
            position = comp.get('position', 'N/A').ljust(10)
            deviation = f"{comp.get('deviation_pct', 0):+.1f}%".rjust(10)
            
            position_icon = '✅' if position.strip() in ['ABOVE', 'BETTER'] else '⚠️'
            
            lines.append(f"{metric} {company_val} {peer_avg}  {position_icon} {position} {deviation}")
        
        return "\n".join(lines)
    
    def generate_uncertainty_section(
        self,
        disclosures: List[str],
        data_availability: Dict[str, bool],
        cached_sources: Optional[Dict[str, bool]] = None,
    ) -> str:
        """Generate uncertainty/missing-data disclosures section."""
        lines = [
            "",
            "-" * 70,
            "              UNCERTAINTY & MISSING DATA DISCLOSURES",
            "-" * 70,
            "",
        ]
        
        # Data availability with cached source detection
        lines.append("Data Availability:")
        for data_type, available in data_availability.items():
            if cached_sources and cached_sources.get(data_type, False):
                status = "✅ Available (Cached)"
            elif available:
                status = "✅ Available"
            else:
                status = "❌ Missing"
            lines.append(f"  - {data_type.replace('_', ' ').title()}: {status}")
        
        lines.append("")
        
        # Specific disclosures
        if disclosures:
            lines.append("Analysis Limitations:")
            for disclosure in disclosures:
                lines.append(f"  - {disclosure}")
        else:
            lines.append("No significant data limitations identified.")
        
        return "\n".join(lines)
    
    def generate_footer(self) -> str:
        """Generate report footer."""
        lines = [
            "",
            "=" * 70,
            "                         END OF REPORT",
            "=" * 70,
            "",
            "Generated by AuditGPT v2.0 - Hybrid Deterministic + AI Forensic Engine",
            "DISCLAIMER: This analysis is for informational purposes only.",
            "            Always verify findings with actual financial statements.",
        ]
        return "\n".join(lines)
    
    def _generate_specific_reasoning(
        self,
        signals: List[Signal],
        sector: str,
    ) -> Optional[str]:
        """Generate specific reasoning paragraph based on signals."""
        if not signals:
            return None
        
        issues = []
        
        # Group by family
        families = {}
        for s in signals:
            family = s.signal_family.value
            if family not in families:
                families[family] = []
            families[family].append(s)
        
        # Build issues list
        if 'revenue_divergence' in families:
            count = len(families['revenue_divergence'])
            issues.append(f"revenue grew faster than cash flow in {count} period(s)")
        
        if 'profit_quality' in families:
            issues.append("profits are not adequately backed by cash generation")
        
        if 'asset_quality' in families or 'npa_spike' in families.get('asset_quality', []):
            issues.append("asset quality deterioration detected")
        
        if 'profitability_collapse' in families:
            issues.append("significant profitability collapse observed")
        
        if 'leverage_stress' in families:
            issues.append("elevated leverage levels")
        
        if not issues:
            return None
        
        if len(issues) == 1:
            return f"Key concern: {issues[0]}."
        elif len(issues) == 2:
            return f"Key concerns: {issues[0]}, and {issues[1]}."
        else:
            return f"Key concerns: {', '.join(issues[:-1])}, and {issues[-1]}."
    
    def _group_signals_by_year(self, signals: List[Signal]) -> Dict[int, List[Signal]]:
        """Group signals by year."""
        by_year = {}
        for signal in signals:
            year = signal.year_latest
            if year not in by_year:
                by_year[year] = []
            by_year[year].append(signal)
        return by_year
