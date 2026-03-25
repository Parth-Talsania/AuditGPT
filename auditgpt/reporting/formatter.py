"""
Report formatting for AuditGPT.

Generates plain-text and JSON output formats.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from datetime import datetime
from enum import Enum

from auditgpt.signals.base import Signal
from auditgpt.scoring.dual_scorer import DualScore
from auditgpt.evidence.models import SentimentTrend
from auditgpt.reporting.sections import ReportSectionGenerator


class FormatType(Enum):
    """Output format types."""
    PLAIN_TEXT = 'plain_text'
    JSON = 'json'
    MARKDOWN = 'markdown'


@dataclass
class ForensicReport:
    """
    Complete forensic analysis report.
    
    Contains all sections and can be rendered in different formats.
    """
    
    # Company info
    ticker: str
    company_name: str
    sector: str
    analysis_date: datetime
    
    # Scores
    dual_score: DualScore
    
    # Signals
    signals: List[Signal] = field(default_factory=list)
    
    # Sections (rendered)
    header: str = ""
    executive_summary: str = ""
    manipulation_signals: str = ""
    stress_signals: str = ""
    red_flag_timeline: str = ""
    auditor_sentiment: str = ""
    rpt_analysis: str = ""
    peer_explanation: str = ""
    peer_comparison: str = ""
    uncertainty_disclosures: str = ""
    footer: str = ""
    
    # Raw data for JSON
    raw_data: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def full_report(self) -> str:
        """Get complete report as plain text."""
        sections = [
            self.header,
            self.executive_summary,
            self.manipulation_signals,
            self.stress_signals,
            self.red_flag_timeline,
            self.auditor_sentiment,
            self.rpt_analysis,
            self.peer_explanation,
            self.peer_comparison,
            self.uncertainty_disclosures,
            self.footer,
        ]
        return "\n".join(s for s in sections if s)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'meta': {
                'ticker': self.ticker,
                'company_name': self.company_name,
                'sector': self.sector,
                'analysis_date': self.analysis_date.isoformat(),
            },
            'scores': self.dual_score.to_dict(),
            'signals': [s.to_dict() for s in self.signals],
            'raw_data': self.raw_data,
        }


class ReportFormatter:
    """
    Formats complete forensic reports.
    
    Combines all sections into final report output.
    """
    
    def __init__(self):
        self.section_gen = ReportSectionGenerator()
    
    def generate_report(
        self,
        company_data: Dict[str, Any],
        ratios: Dict[str, Any],
        signals: List[Signal],
        dual_score: DualScore,
        peer_comparison: Optional[Dict[str, Any]] = None,
        sentiment_trend: Optional[SentimentTrend] = None,
        rpt_data: Optional[Dict[str, Any]] = None,
        peer_explanation: str = "",
        data_availability: Optional[Dict[str, bool]] = None,
        uncertainty_disclosures: Optional[List[str]] = None,
        has_real_notes: bool = False,
    ) -> ForensicReport:
        """
        Generate complete forensic report.
        
        Args:
            company_data: Company information dict
            ratios: Financial ratios dict
            signals: List of detected signals
            dual_score: Dual manipulation/stress scores
            peer_comparison: Peer benchmark data
            sentiment_trend: Auditor sentiment trend
            rpt_data: Related party / Other Income data
            peer_explanation: Explanation of peer selection
            data_availability: What data was available
            uncertainty_disclosures: List of uncertainty statements
            has_real_notes: Whether real annual report notes were parsed
            
        Returns:
            ForensicReport with all sections
        """
        ticker = company_data.get('ticker', 'UNKNOWN')
        company_name = company_data.get('name', ticker)
        sector = company_data.get('sector', 'DEFAULT')
        
        # Default data availability if not provided
        if data_availability is None:
            data_availability = {
                'pnl': company_data.get('pnl') is not None,
                'balance_sheet': company_data.get('balance_sheet') is not None,
                'cash_flow': company_data.get('cash_flow') is not None,
                'ratios': company_data.get('ratios') is not None,
                'auditor_notes': has_real_notes,
            }
        
        # Default disclosures
        if uncertainty_disclosures is None:
            uncertainty_disclosures = []
            if not has_real_notes:
                uncertainty_disclosures.append(
                    "Auditor note sentiment based on proxy data - actual notes not parsed."
                )
                uncertainty_disclosures.append(
                    "RPT analysis uses Other Income as proxy - actual RPT notes not parsed."
                )
        
        # Generate all sections
        report = ForensicReport(
            ticker=ticker,
            company_name=company_name,
            sector=sector,
            analysis_date=datetime.now(),
            dual_score=dual_score,
            signals=signals,
        )
        
        report.header = self.section_gen.generate_header(company_data)
        
        report.executive_summary = self.section_gen.generate_executive_summary(
            dual_score=dual_score,
            signals=signals,
            sector=sector,
        )
        
        report.manipulation_signals = self.section_gen.generate_manipulation_signals_section(
            signals=signals,
        )
        
        report.stress_signals = self.section_gen.generate_stress_signals_section(
            signals=signals,
        )
        
        report.red_flag_timeline = self.section_gen.generate_red_flag_timeline(
            signals=signals,
        )
        
        report.auditor_sentiment = self.section_gen.generate_auditor_sentiment_section(
            sentiment_trend=sentiment_trend,
            has_real_notes=has_real_notes,
        )
        
        report.rpt_analysis = self.section_gen.generate_rpt_section(
            rpt_data=rpt_data,
            has_real_rpt_notes=has_real_notes,  # Same flag for now
            signals=signals,
        )
        
        peers_used = peer_comparison.get('peers', []) if peer_comparison else []
        report.peer_explanation = self.section_gen.generate_peer_explanation_section(
            peer_selection_explanation=peer_explanation,
            peers_used=peers_used,
        )
        
        report.peer_comparison = self.section_gen.generate_peer_comparison_table(
            peer_comparison=peer_comparison,
        )
        
        report.uncertainty_disclosures = self.section_gen.generate_uncertainty_section(
            disclosures=uncertainty_disclosures,
            data_availability=data_availability,
        )
        
        report.footer = self.section_gen.generate_footer()
        
        # Store raw data
        report.raw_data = {
            'ratios': self._serialize_ratios(ratios),
            'peer_comparison': peer_comparison,
            'rpt_data': rpt_data,
        }
        
        return report
    
    def _serialize_ratios(self, ratios: Dict[str, Any]) -> Dict[str, Any]:
        """Serialize ratios for JSON output."""
        serialized = {}
        for key, value in ratios.items():
            if isinstance(value, dict):
                serialized[key] = {str(k): v for k, v in value.items()}
            else:
                serialized[key] = value
        return serialized
    
    def generate_legacy_report(
        self,
        company_data: Dict[str, Any],
        ratios: Dict[str, Any],
        anomalies: List[Dict[str, Any]],
        peer_comparison: Optional[Dict[str, Any]] = None,
        risk_score: float = 0,
        risk_level: str = 'LOW',
        auditor_sentiment: Optional[Dict[str, Any]] = None,
        rpt_growth_data: Optional[Dict[str, Any]] = None,
    ) -> str:
        """
        Generate legacy-format report for backward compatibility.
        
        This matches the output format of the original audit_gpt.py.
        """
        # Convert legacy anomalies to signals for processing
        # (This is a simplified conversion for compatibility)
        
        report = []
        report.append("=" * 70)
        report.append("                    AUDITGPT FORENSIC ANALYSIS REPORT")
        report.append("=" * 70)
        report.append(f"\nCompany: {company_data.get('name', company_data.get('ticker', 'Unknown'))}")
        report.append(f"Ticker: {company_data.get('ticker', 'N/A')}")
        report.append(f"Sector: {company_data.get('sector', 'Unknown')}")
        report.append(f"Analysis Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Risk Score
        report.append("\n" + "-" * 70)
        report.append("                         FRAUD RISK ASSESSMENT")
        report.append("-" * 70)
        
        risk_emoji = {'CRITICAL': '🔴', 'HIGH': '🟠', 'MEDIUM': '🟡', 'LOW': '🟢'}
        report.append(f"\n{risk_emoji.get(risk_level, '⚪')} FRAUD RISK SCORE: {risk_score}/100 ({risk_level})")
        
        # Anomalies
        report.append("\n" + "-" * 70)
        report.append("              RED FLAG TIMELINE")
        report.append("-" * 70)
        
        if anomalies:
            by_year = {}
            for a in anomalies:
                year = a.get('year', 'Unknown')
                if year not in by_year:
                    by_year[year] = []
                by_year[year].append(a)
            
            for year in sorted(by_year.keys()):
                report.append(f"\n{year}:")
                for a in by_year[year]:
                    severity = a.get('severity', 'LOW')
                    icon = {'CRITICAL': '🔴', 'HIGH': '🟠', 'MEDIUM': '🟡', 'LOW': '🟢', 'INFO': '🟦'}.get(severity, '⚪')
                    report.append(f"   {icon} [{severity}] {a.get('description', '')}")
                    if a.get('source_reference'):
                        report.append(f"      Source: {a.get('source_reference')}")
        else:
            report.append("\nNo red flags detected.")
        
        # Peer comparison
        if peer_comparison and peer_comparison.get('peers'):
            report.append("\n" + "-" * 70)
            report.append("                       PEER COMPARISON")
            report.append("-" * 70)
            report.append(f"\nPeers: {', '.join(peer_comparison['peers'])}")
        
        report.append("\n" + "=" * 70)
        report.append("                         END OF REPORT")
        report.append("=" * 70)
        
        return "\n".join(report)
    
    def format_report(
        self,
        sections: Dict[str, str],
        company: str,
        format_type: FormatType = FormatType.PLAIN_TEXT,
    ) -> str:
        """
        Format report sections into final output.
        
        Args:
            sections: Dictionary of report sections
            company: Company ticker
            format_type: Output format type
            
        Returns:
            Formatted report string
        """
        if format_type == FormatType.JSON:
            import json
            return json.dumps(sections, indent=2)
        
        # Plain text format
        report_lines = []
        
        report_lines.append("=" * 70)
        report_lines.append("          AUDITGPT v2.0 FORENSIC ANALYSIS REPORT")
        report_lines.append("=" * 70)
        report_lines.append(f"\nCompany: {company}")
        report_lines.append(f"Analysis Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report_lines.append("")
        
        # Add each section
        section_order = [
            'executive_summary',
            'manipulation_signals', 
            'stress_signals',
            'timeline',
            'auditor_sentiment',
            'rpt_trend',
            'peer_selection',
            'peer_comparison',
            'missing_data',
        ]
        
        for section_key in section_order:
            if section_key in sections and sections[section_key]:
                report_lines.append("")
                report_lines.append("-" * 70)
                report_lines.append(sections[section_key])
        
        report_lines.append("")
        report_lines.append("=" * 70)
        report_lines.append("                    END OF REPORT")
        report_lines.append("=" * 70)
        
        return "\n".join(report_lines)

