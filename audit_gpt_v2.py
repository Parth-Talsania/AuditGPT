#!/usr/bin/env python3
"""
AuditGPT - Financial Statement Forensics Engine
"The AI That Reads 10 Years of Financial Statements and Finds What the Auditors Missed"

This is the backward-compatible entrypoint that wraps the new modular auditgpt package.

For new integrations, prefer using:
    from auditgpt import AuditGPT
    engine = AuditGPT()
    result = engine.analyze("HDFCBANK")
"""

import warnings
import sys
import os

warnings.filterwarnings('ignore')

# Ensure auditgpt package is importable
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from auditgpt.api.engine import AuditGPT as ModularAuditGPT, AnalysisResult

# Re-export for backward compatibility
__all__ = ['AuditGPT', 'run_audit']


class AuditGPT:
    """
    Backward-compatible AuditGPT wrapper.
    
    This class provides the same interface as the original audit_gpt.py
    while using the new modular implementation under the hood.
    
    Features (v2.0):
    - Dual scoring (manipulation vs stress) - mandatory for banks
    - Evidence-first architecture with citations
    - Real PDF parsing when available
    - Dynamic peer selection with robust statistics
    - Explicit "data unavailable" flags (no fabrication)
    """
    
    def __init__(self, verbose: bool = True, cache_dir: str = ".cache/auditgpt"):
        """
        Initialize AuditGPT engine.
        
        Args:
            verbose: Whether to print progress messages
            cache_dir: Directory for caching scraped data
        """
        self.verbose = verbose
        self._engine = ModularAuditGPT(
            cache_dir=cache_dir,
            enable_caching=True,
            verbose=verbose,
        )
    
    def analyze(self, ticker: str, sector: str = None, peers: list = None) -> dict:
        """
        Analyze a company for forensic red flags.
        
        Args:
            ticker: Company ticker symbol (e.g., "HDFCBANK", "TCS", "YESBANK")
            sector: Optional sector override (auto-detected if not provided)
            peers: Optional list of peer company tickers
            
        Returns:
            Dictionary with analysis results including:
            - ticker: Company ticker
            - sector: Detected sector
            - risk_score: Combined risk score (0-100)
            - risk_level: Risk level (LOW/MEDIUM/HIGH/CRITICAL)
            - dual_score: Separate manipulation and stress scores
            - anomalies: List of detected anomalies/signals
            - peer_comparison: Peer benchmarking results
            - auditor_sentiment: Auditor sentiment analysis (or unavailable flag)
            - report: Full text report
        """
        try:
            # Call the modular engine
            result = self._engine.analyze(
                company=ticker,
                sector=sector,
                peers=peers,
            )
            
            if not result.success:
                if self.verbose:
                    print(f"[AuditGPT] Analysis failed: {result.error_message}")
                return None
            
            # Convert to legacy format for backward compatibility
            return self._convert_to_legacy_format(result)
            
        except Exception as e:
            if self.verbose:
                print(f"[AuditGPT] Error during analysis: {e}")
            return None
    
    def _convert_to_legacy_format(self, result: AnalysisResult) -> dict:
        """Convert new AnalysisResult to legacy dictionary format."""
        # Build anomalies list from signals
        anomalies = []
        for signal in result.all_signals:
            anomaly = {
                'type': signal.signal_family.value,
                'year': signal.year_latest,
                'severity': signal.current_severity.value,
                'category': signal.manipulation_or_stress.value,
                'description': signal.explanation_seed,
                'evidence': [e.citation_string for e in signal.evidence_refs],
            }
            anomalies.append(anomaly)
        
        # Build peer comparison
        peer_comparison = {
            'peers': [
                {
                    'company': pm.ticker,
                    'sector': pm.sector,
                    'match_score': pm.match_score,
                    'reason': pm.selection_explanation,
                }
                for pm in result.peer_matches
            ],
            # Extract only the actual benchmark metrics, not metadata
            'benchmarks': result.peer_benchmarks.to_dict().get('benchmarks', {}) if result.peer_benchmarks else {},
        }
        
        # Build ratios (from scoring breakdown if available)
        ratios = {}
        if result.dual_score and result.dual_score.score_breakdown:
            ratios = result.dual_score.score_breakdown
        
        # Extract RPT data from sentiment_result if available (from qualitative cache)
        rpt_data = {}
        if result.sentiment_result:
            if result.sentiment_result.get('has_rpt_notes'):
                rpt_data = {
                    'status': 'Available (Cached)',
                    'notes': result.sentiment_result.get('rpt_data', {}),
                }
            elif result.sentiment_result.get('rpt_data'):
                rpt_data = {
                    'status': 'Available',
                    'notes': result.sentiment_result.get('rpt_data', {}),
                }
        
        # Generate XAI trace for weight contribution visualization
        xai_trace = self._generate_xai_trace(result)
        
        return {
            'ticker': result.company,
            'name': result.company,  # Name not always available
            'sector': result.sector,
            'risk_score': result.dual_score.combined_score if result.dual_score else 0,
            'risk_level': result.dual_score.combined_level if result.dual_score else 'LOW',
            'dual_score': {
                'manipulation_score': result.dual_score.manipulation_score if result.dual_score else 0,
                'manipulation_level': result.dual_score.manipulation_level if result.dual_score else 'LOW',
                'stress_score': result.dual_score.stress_score if result.dual_score else 0,
                'stress_level': result.dual_score.stress_level if result.dual_score else 'LOW',
            },
            'anomalies': anomalies,
            'peer_comparison': peer_comparison,
            'ratios': ratios,
            'auditor_sentiment': result.sentiment_result,
            'rpt_growth_data': rpt_data,  # Now populated from cache if available
            'xai_trace': xai_trace,  # XAI weight contribution trace
            'missing_data': result.missing_data,
            'timing': result.timing.to_dict() if result.timing else {},
            'report': result.full_report,
        }
    
    def _generate_xai_trace(self, result: AnalysisResult) -> dict:
        """
        Generate XAI trace for explainable weight contribution visualization.
        
        For deterministic rule engines, XAI must trace the exact mathematical
        weights contributing to the score rather than using statistical methods
        like SHAP or LIME.
        """
        if not result.all_signals:
            return {
                'primary_driver': 'No anomalies detected',
                'evidence_chain': [],
                'logical_rule_triggered': None,
                'signal_contributions': [],
            }
        
        # Sort signals by severity weight (CRITICAL=4, HIGH=3, MEDIUM=2, LOW=1)
        severity_weights = {'CRITICAL': 4, 'HIGH': 3, 'MEDIUM': 2, 'LOW': 1, 'INFO': 0}
        sorted_signals = sorted(
            result.all_signals,
            key=lambda x: severity_weights.get(x.current_severity.value, 0),
            reverse=True
        )
        
        top_signal = sorted_signals[0]
        
        # Calculate contribution percentages
        total_weight = sum(
            severity_weights.get(s.current_severity.value, 0)
            for s in result.all_signals
        )
        
        signal_contributions = []
        for signal in sorted_signals[:5]:  # Top 5 signals
            weight = severity_weights.get(signal.current_severity.value, 0)
            contribution_pct = (weight / total_weight * 100) if total_weight > 0 else 0
            # Use description (explanation_seed may be empty)
            desc = signal.description or signal.explanation_seed or 'N/A'
            signal_contributions.append({
                'signal_family': signal.signal_family.value,
                'year': signal.year_latest,
                'severity': signal.current_severity.value,
                'contribution_pct': round(contribution_pct, 1),
                'description': desc[:100] if desc else 'N/A',
            })
        
        # Get top signal description for rule triggered
        top_desc = top_signal.description or top_signal.explanation_seed or None
        
        return {
            'primary_driver': f"{top_signal.signal_family.value} in FY{top_signal.year_latest}",
            'evidence_chain': [e.citation_string for e in top_signal.evidence_refs][:3],
            'logical_rule_triggered': top_desc[:150] if top_desc else None,
            'signal_contributions': signal_contributions,
        }
    
    def quick_score(self, ticker: str, sector: str = None) -> dict:
        """
        Get quick dual score without full report generation.
        
        Args:
            ticker: Company ticker
            sector: Optional sector override
            
        Returns:
            Dictionary with dual scores
        """
        dual_score = self._engine.get_quick_score(ticker, sector)
        
        if dual_score:
            return {
                'ticker': ticker,
                'manipulation_score': dual_score.manipulation_score,
                'manipulation_level': dual_score.manipulation_level,
                'stress_score': dual_score.stress_score,
                'stress_level': dual_score.stress_level,
                'combined_score': dual_score.combined_score,
                'combined_level': dual_score.combined_level,
            }
        return None
    
    def batch_analyze(self, tickers: list, sector: str = None) -> list:
        """
        Analyze multiple companies.
        
        Args:
            tickers: List of company tickers
            sector: Optional sector override for all
            
        Returns:
            List of analysis results
        """
        results = []
        for ticker in tickers:
            if self.verbose:
                print(f"\n[AuditGPT] Analyzing {ticker}...")
            result = self.analyze(ticker, sector)
            if result:
                results.append(result)
        return results


def run_audit(ticker: str, verbose: bool = True) -> str:
    """
    Legacy function to run audit and return report string.
    
    Args:
        ticker: Company ticker
        verbose: Whether to print progress
        
    Returns:
        Full report as string
    """
    engine = AuditGPT(verbose=verbose)
    result = engine.analyze(ticker)
    
    if result:
        return result['report']
    return f"Analysis failed for {ticker}"


# ============================================
# MAIN EXECUTION
# ============================================

if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("          AUDITGPT v2.0 - FINANCIAL STATEMENT FORENSICS ENGINE")
    print("   'The AI That Reads 10 Years of Financial Statements")
    print("    and Finds What the Auditors Missed'")
    print("=" * 70)
    print("\n🆕 New in v2.0:")
    print("   • Dual scoring: Manipulation risk vs Financial stress")
    print("   • Evidence-backed citations for all signals")
    print("   • Bank-specific analysis (NPA, CAR, etc.)")
    print("   • No fabricated data - explicit 'unavailable' flags")
    print("-" * 70)
    
    # Initialize engine
    engine = AuditGPT()
    
    # Demo with known fraud case
    print("\n📌 DEMO: Analyzing YES BANK (known fraud case)")
    print("-" * 50)
    
    result = engine.analyze("YESBANK")
    if result:
        print(result['report'])
        
        # Print dual score summary
        print("\n" + "=" * 50)
        print("📊 DUAL SCORE SUMMARY:")
        print("-" * 50)
        ds = result.get('dual_score', {})
        print(f"   Manipulation Score: {ds.get('manipulation_score', 'N/A')} ({ds.get('manipulation_level', 'N/A')})")
        print(f"   Stress Score:       {ds.get('stress_score', 'N/A')} ({ds.get('stress_level', 'N/A')})")
        print(f"   Combined Score:     {result.get('risk_score', 'N/A')} ({result.get('risk_level', 'N/A')})")
        
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
            
            # Print dual score summary
            print("\n" + "=" * 50)
            print("📊 DUAL SCORE SUMMARY:")
            print("-" * 50)
            ds = result.get('dual_score', {})
            print(f"   Manipulation Score: {ds.get('manipulation_score', 'N/A')} ({ds.get('manipulation_level', 'N/A')})")
            print(f"   Stress Score:       {ds.get('stress_score', 'N/A')} ({ds.get('stress_level', 'N/A')})")
            print(f"   Combined Score:     {result.get('risk_score', 'N/A')} ({result.get('risk_level', 'N/A')})")
            
            # Save report
            filename = f"{user_input}_audit_report.txt"
            with open(filename, 'w') as f:
                f.write(result['report'])
            print(f"\n💾 Report saved to {filename}")
    
    print("\n🎯 AUDITGPT v2.0 Analysis Complete.")
