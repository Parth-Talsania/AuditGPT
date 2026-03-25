"""
AuditGPT Main Engine - Central Facade

"The AI That Reads 10 Years of Financial Statements and Finds What the Auditors Missed"

This is the main entry point for the AuditGPT forensic analysis engine.
It orchestrates all modules to produce a comprehensive forensic audit report.

Key principles:
1. Evidence-first: Every signal must reference its source
2. Benchmark-first: All thresholds are sector/peer-aware
3. No fabrication: Explicit "data unavailable" when missing
4. Bank separation: Stress vs manipulation scores mandatory for banks
5. Deterministic math: AI only for NLP/retrieval/explanation
6. Sub-90s goal: Caching at every layer
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any, Tuple
import time
import traceback

# Config
from auditgpt.config.constants import SECTOR_MAPPING, BANK_SECTORS, PEER_GROUPS
from auditgpt.config.thresholds import SectorThresholds, should_skip_cfo_analysis, should_skip_rpt_proxy

# Data ingestion
from auditgpt.ingestion.screener import DataAcquisition
from auditgpt.ingestion.csv_loader import CSVLoader
from auditgpt.ingestion.cache import CacheManager

# Evidence
from auditgpt.evidence.models import EvidenceRef, NoteChunk, RefType
from auditgpt.evidence.store import EvidenceStore

# Signal detection
from auditgpt.signals.base import Signal, SignalSeverity, SignalCategory, SignalFamily
from auditgpt.signals import ManipulationDetector, StressDetector, BankSignalDetector

# Scoring
from auditgpt.scoring.dual_scorer import DualScorer, DualScore

# Peer benchmarking
from auditgpt.benchmarking.peer_selector import PeerSelector, PeerMatch
from auditgpt.benchmarking.peer_stats import PeerStats, PeerBenchmarks

# AI/NLP
from auditgpt.ai.sentiment import AuditorSentimentAnalyzer
from auditgpt.ai.retriever import HybridRetriever

# Reporting
from auditgpt.reporting.sections import ReportSectionGenerator
from auditgpt.reporting.formatter import ReportFormatter, FormatType

# PDF extraction (optional)
from auditgpt.extraction.pdf_parser import PDFParser
from auditgpt.extraction.section_detector import SectionDetector
from auditgpt.extraction.note_normalizer import NoteNormalizer


@dataclass
class AnalysisTiming:
    """Timing instrumentation for performance tracking."""
    data_fetch_ms: int = 0
    ratio_calc_ms: int = 0
    peer_benchmark_ms: int = 0
    anomaly_detection_ms: int = 0
    sentiment_analysis_ms: int = 0
    report_generation_ms: int = 0
    total_ms: int = 0
    
    def to_dict(self) -> Dict[str, int]:
        return {
            'data_fetch_ms': self.data_fetch_ms,
            'ratio_calc_ms': self.ratio_calc_ms,
            'peer_benchmark_ms': self.peer_benchmark_ms,
            'anomaly_detection_ms': self.anomaly_detection_ms,
            'sentiment_analysis_ms': self.sentiment_analysis_ms,
            'report_generation_ms': self.report_generation_ms,
            'total_ms': self.total_ms,
        }


@dataclass
class AnalysisResult:
    """Complete analysis result with dual scores and full report."""
    company: str
    sector: str
    analysis_year: int
    
    # Dual scores
    dual_score: DualScore = None
    
    # Signal breakdown
    manipulation_signals: List[Signal] = field(default_factory=list)
    stress_signals: List[Signal] = field(default_factory=list)
    all_signals: List[Signal] = field(default_factory=list)
    
    # Peer analysis
    peer_matches: List[PeerMatch] = field(default_factory=list)
    peer_benchmarks: PeerBenchmarks = None
    
    # Sentiment analysis (with data availability flag)
    sentiment_result: Dict[str, Any] = field(default_factory=dict)
    
    # Report sections
    report_sections: Dict[str, str] = field(default_factory=dict)
    full_report: str = ""
    
    # Missing data disclosures
    missing_data: List[str] = field(default_factory=list)
    
    # Performance timing
    timing: AnalysisTiming = None
    
    # Success flag
    success: bool = True
    error_message: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'company': self.company,
            'sector': self.sector,
            'analysis_year': self.analysis_year,
            'dual_score': self.dual_score.to_dict() if self.dual_score else None,
            'manipulation_signals': [
                {
                    'id': s.signal_id,
                    'family': s.signal_family.value,
                    'severity': s.current_severity.value,
                    'explanation': s.explanation_seed,
                    'evidence': [e.citation_string for e in s.evidence_refs],
                }
                for s in self.manipulation_signals
            ],
            'stress_signals': [
                {
                    'id': s.signal_id,
                    'family': s.signal_family.value,
                    'severity': s.current_severity.value,
                    'explanation': s.explanation_seed,
                    'evidence': [e.citation_string for e in s.evidence_refs],
                }
                for s in self.stress_signals
            ],
            'peer_matches': [
                {'company': p.ticker, 'sector': p.sector, 'score': p.match_score, 'reason': p.selection_explanation}
                for p in self.peer_matches
            ],
            'sentiment_result': self.sentiment_result,
            'missing_data': self.missing_data,
            'timing': self.timing.to_dict() if self.timing else None,
            'success': self.success,
            'error_message': self.error_message,
        }


class AuditGPT:
    """
    Main AuditGPT forensic analysis engine.
    
    Usage:
        engine = AuditGPT()
        result = engine.analyze("HDFCBANK")
        print(result.full_report)
    """
    
    def __init__(
        self,
        cache_dir: str = ".cache/auditgpt",
        enable_caching: bool = True,
        pdf_dir: Optional[str] = None,
        verbose: bool = False,
    ):
        """
        Initialize the AuditGPT engine.
        
        Args:
            cache_dir: Directory for caching scraped data
            enable_caching: Whether to use caching
            pdf_dir: Directory containing annual report PDFs (optional)
            verbose: Whether to print progress messages
        """
        self.verbose = verbose
        self.pdf_dir = pdf_dir
        
        # Initialize components
        self.cache_manager = CacheManager(cache_dir) if enable_caching else None
        self.data_acquisition = DataAcquisition()
        self.csv_loader = CSVLoader()
        
        # Evidence and retrieval
        self.evidence_store = EvidenceStore()
        self.retriever = HybridRetriever(self.evidence_store)
        
        # Signal detectors
        self.manipulation_detector = ManipulationDetector()
        self.stress_detector = StressDetector()
        self.bank_detector = BankSignalDetector()
        
        # Scoring
        self.scorer = DualScorer()
        
        # Peer analysis
        self.peer_selector = PeerSelector()
        self.peer_stats = PeerStats()
        
        # Sentiment analysis
        self.sentiment_analyzer = AuditorSentimentAnalyzer()
        
        # PDF parsing (optional)
        self.pdf_parser = PDFParser() if pdf_dir else None
        self.section_detector = SectionDetector()
        self.note_normalizer = NoteNormalizer()
        
        # Reporting
        self.report_generator = ReportSectionGenerator()
        self.report_formatter = ReportFormatter()
        
        # Sector thresholds
        self.thresholds = SectorThresholds()
    
    def _log(self, message: str):
        """Log message if verbose mode enabled."""
        if self.verbose:
            print(f"[AuditGPT] {message}")
    
    def analyze(
        self,
        company: str,
        sector: Optional[str] = None,
        peers: Optional[List[str]] = None,
        pdf_path: Optional[str] = None,
        current_year: int = 2025,
    ) -> AnalysisResult:
        """
        Perform comprehensive forensic analysis on a company.
        
        Args:
            company: Company ticker (e.g., "HDFCBANK", "TCS")
            sector: Sector code override (auto-detected if not provided)
            peers: Optional list of peer companies for comparison
            pdf_path: Path to annual report PDF (optional)
            current_year: Current fiscal year for analysis
            
        Returns:
            AnalysisResult with dual scores, signals, and full report
        """
        timing = AnalysisTiming()
        start_time = time.time()
        
        result = AnalysisResult(
            company=company,
            sector="",
            analysis_year=current_year,
            timing=timing,
        )
        
        try:
            # Phase 1: Data Acquisition
            self._log(f"Fetching data for {company}...")
            t0 = time.time()
            
            company_data = self._fetch_company_data(company)
            if not company_data:
                result.success = False
                result.error_message = f"Failed to fetch data for {company}"
                return result
            
            timing.data_fetch_ms = int((time.time() - t0) * 1000)
            
            # Phase 2: Determine sector
            detected_sector = self._detect_sector(company, sector)
            result.sector = detected_sector
            is_bank = detected_sector in BANK_SECTORS
            
            self._log(f"Detected sector: {detected_sector} (is_bank={is_bank})")
            
            # Phase 3: Calculate ratios
            self._log("Calculating financial ratios...")
            t0 = time.time()
            
            ratios = self._calculate_ratios(company_data, detected_sector)
            
            timing.ratio_calc_ms = int((time.time() - t0) * 1000)
            
            # Phase 4: Peer benchmarking
            self._log("Running peer benchmarking...")
            t0 = time.time()
            
            peer_matches, peer_benchmarks, peer_comparison = self._run_peer_analysis(
                company, detected_sector, ratios, peers
            )
            result.peer_matches = peer_matches
            result.peer_benchmarks = peer_benchmarks
            
            timing.peer_benchmark_ms = int((time.time() - t0) * 1000)
            
            # Phase 5: Signal detection
            self._log("Detecting forensic signals...")
            t0 = time.time()
            
            all_signals = self._detect_signals(
                company_data, ratios, detected_sector, peer_benchmarks, current_year
            )
            result.all_signals = all_signals
            
            # Separate signals by category
            result.manipulation_signals = [
                s for s in all_signals
                if s.manipulation_or_stress in (SignalCategory.MANIPULATION, SignalCategory.BOTH)
            ]
            result.stress_signals = [
                s for s in all_signals
                if s.manipulation_or_stress in (SignalCategory.STRESS, SignalCategory.BOTH)
            ]
            
            timing.anomaly_detection_ms = int((time.time() - t0) * 1000)
            
            # Phase 6: Sentiment analysis
            self._log("Analyzing auditor sentiment...")
            t0 = time.time()
            
            sentiment_result = self._analyze_sentiment(company, pdf_path, current_year)
            result.sentiment_result = sentiment_result
            
            timing.sentiment_analysis_ms = int((time.time() - t0) * 1000)
            
            # Phase 7: Dual scoring
            self._log("Computing dual scores...")
            
            dual_score = self.scorer.score(
                signals=all_signals,
                peer_comparison=peer_comparison,
                current_year=current_year,
                sector=detected_sector,
            )
            result.dual_score = dual_score
            
            # Phase 8: Report generation
            self._log("Generating forensic report...")
            t0 = time.time()
            
            report_sections, full_report, missing_data = self._generate_report(
                result, company_data, ratios, peer_comparison, sentiment_result
            )
            result.report_sections = report_sections
            result.full_report = full_report
            result.missing_data = missing_data
            
            timing.report_generation_ms = int((time.time() - t0) * 1000)
            
            timing.total_ms = int((time.time() - start_time) * 1000)
            
            self._log(f"Analysis complete in {timing.total_ms}ms")
            
            return result
            
        except Exception as e:
            result.success = False
            result.error_message = f"Analysis failed: {str(e)}\n{traceback.format_exc()}"
            timing.total_ms = int((time.time() - start_time) * 1000)
            return result
    
    def _fetch_company_data(self, company: str) -> Optional[Dict[str, Any]]:
        """Fetch financial data for company from screener.in or cache."""
        # Try cache first
        if self.cache_manager:
            cached = self.cache_manager.get_company_data(company)
            if cached:
                return cached
        
        # Fetch fresh data
        try:
            data = self.data_acquisition.fetch_all_data(company)
            
            if data and self.cache_manager:
                self.cache_manager.set_company_data(company, data)
            
            return data
        except Exception as e:
            self._log(f"Error fetching data: {e}")
            return None
    
    def _detect_sector(self, company: str, override: Optional[str] = None) -> str:
        """Detect company sector from mapping or override."""
        if override:
            return override.upper()
        
        # Check known mapping
        if company.upper() in SECTOR_MAPPING:
            return SECTOR_MAPPING[company.upper()]
        
        # Default sector
        return "DEFAULT"
    
    def _calculate_ratios(self, company_data: Dict[str, Any], sector: str) -> Dict[str, Any]:
        """Calculate financial ratios from company data."""
        ratios = {}
        
        pnl = company_data.get('pnl', {})
        balance_sheet = company_data.get('balance_sheet', {})
        cash_flow = company_data.get('cash_flow', {})
        years = company_data.get('years', [])
        
        # Convert DataFrames to dicts if needed
        if hasattr(pnl, 'to_dict'):
            pnl = pnl.to_dict(orient='list')
        if hasattr(balance_sheet, 'to_dict'):
            balance_sheet = balance_sheet.to_dict(orient='list')
        if hasattr(cash_flow, 'to_dict'):
            cash_flow = cash_flow.to_dict(orient='list')
        
        # Get years from data if not provided
        if not years and pnl:
            # Try to get years from first column of pnl
            first_key = next(iter(pnl.keys()), None)
            if first_key and isinstance(pnl[first_key], list):
                years = [str(i) for i in range(len(pnl[first_key]))]
        
        # Revenue and growth
        revenue = pnl.get('Revenue+', pnl.get('Revenue', pnl.get('Sales', [])))
        if revenue and len(revenue) >= 2:
            ratios['revenue_growth'] = self._calculate_growth(revenue)
            ratios['revenue_values'] = revenue
        
        # Net profit
        net_profit = pnl.get('Net Profit+', pnl.get('Net Profit', pnl.get('Profit after Tax', [])))
        if net_profit:
            ratios['net_profit'] = net_profit
            if len(net_profit) >= 2:
                ratios['np_growth'] = self._calculate_growth(net_profit)
        
        # Operating Profit (for OPM)
        operating_profit = pnl.get('Operating Profit', pnl.get('Financing Profit', []))
        if operating_profit and revenue:
            ratios['opm'] = [
                (op / r * 100) if r and r != 0 else None
                for op, r in zip(operating_profit, revenue)
            ]
        
        # CFO
        cfo = cash_flow.get('Cash from Operating Activity', cash_flow.get('CFO', []))
        if cfo:
            ratios['cfo'] = cfo
            if net_profit and len(cfo) == len(net_profit):
                ratios['cfo_np_ratio'] = [
                    c / n if n and n != 0 else None
                    for c, n in zip(cfo, net_profit)
                ]
        
        # Receivables (Debtors)
        debtors = balance_sheet.get('Trade Receivables', balance_sheet.get('Debtors', []))
        if debtors and revenue:
            ratios['debtor_days'] = [
                (d / r * 365) if r and r != 0 else None
                for d, r in zip(debtors, revenue)
            ]
        
        # Debt/Equity
        total_debt = balance_sheet.get('Borrowings', balance_sheet.get('Total Debt', []))
        equity = balance_sheet.get('Share Capital', balance_sheet.get('Equity', []))
        if total_debt and equity:
            ratios['debt_equity'] = [
                d / e if e and e != 0 else None
                for d, e in zip(total_debt, equity)
            ]
        
        # ROCE
        profit_before_tax = pnl.get('Profit before tax', pnl.get('PBT', []))
        capital_employed = balance_sheet.get('Capital Employed', balance_sheet.get('Total Assets', []))
        if profit_before_tax and capital_employed:
            ratios['roce'] = [
                (pbt / ce * 100) if ce and ce != 0 else None
                for pbt, ce in zip(profit_before_tax, capital_employed)
            ]
        
        # Interest coverage
        interest = pnl.get('Interest', pnl.get('Finance Costs', []))
        if operating_profit and interest:
            ratios['interest_coverage'] = [
                op / i if i and i > 0 else None
                for op, i in zip(operating_profit, interest)
            ]
        
        # Bank-specific ratios
        if sector in BANK_SECTORS:
            gnpa = pnl.get('GNPA %', pnl.get('Gross NPA %', []))
            nnpa = pnl.get('NNPA %', pnl.get('Net NPA %', []))
            car = balance_sheet.get('CAR %', balance_sheet.get('Capital Adequacy Ratio', []))
            nim = pnl.get('NIM %', pnl.get('Net Interest Margin', []))
            
            if gnpa:
                ratios['gnpa'] = gnpa
            if nnpa:
                ratios['nnpa'] = nnpa
            if car:
                ratios['car'] = car
            if nim:
                ratios['nim'] = nim
        
        # Other income for manipulation proxy (non-banks only)
        if not should_skip_rpt_proxy(sector):
            other_income = pnl.get('Other Income', [])
            pbt = pnl.get('Profit Before Tax', pnl.get('PBT', []))
            if other_income and pbt:
                ratios['other_income_pbt_ratio'] = [
                    o / p if p and p != 0 else None
                    for o, p in zip(other_income, pbt)
                ]
        
        ratios['years'] = years if years else list(range(len(revenue))) if revenue else []
        
        return ratios
    
    def _calculate_growth(self, values: List[float]) -> List[Optional[float]]:
        """Calculate YoY growth rates."""
        growth = []
        for i in range(len(values)):
            if i == 0:
                growth.append(None)
            elif values[i-1] and values[i-1] > 0:
                growth.append((values[i] - values[i-1]) / values[i-1] * 100)
            else:
                growth.append(None)
        return growth
    
    def _run_peer_analysis(
        self,
        company: str,
        sector: str,
        ratios: Dict[str, Any],
        override_peers: Optional[List[str]] = None,
    ) -> Tuple[List[PeerMatch], Optional[PeerBenchmarks], Dict[str, Any]]:
        """Run peer selection and benchmarking."""
        selection_explanation = ""
        
        # Select peers
        if override_peers:
            peer_matches = [
                PeerMatch(ticker=p, sector=sector, match_score=1.0, selection_explanation="User specified")
                for p in override_peers
            ]
            selection_explanation = "User specified peers"
        else:
            peer_matches, selection_explanation = self.peer_selector.select_peers(
                target_ticker=company,
                target_sector=sector,
                target_revenue=ratios.get('revenue_values', [])[-1] if ratios.get('revenue_values') else None,
            )
        
        if not peer_matches:
            return [], None, {'explanation': selection_explanation, 'peers': []}
        
        # Fetch peer data and compute stats
        peer_data = {}
        for pm in peer_matches:
            try:
                pdata = self._fetch_company_data(pm.ticker)
                if pdata:
                    pratios = self._calculate_ratios(pdata, pm.sector)
                    peer_data[pm.ticker] = pratios
            except Exception:
                pass
        
        if not peer_data:
            return peer_matches, None, {'explanation': selection_explanation, 'peers': [pm.ticker for pm in peer_matches]}
        
        # Compute peer benchmarks
        benchmarks = self.peer_stats.compute_benchmarks(
            company_ticker=company,
            company_ratios=ratios,
            peer_ratios=peer_data,
            sector=sector,
        )
        
        # Build comparison result
        comparison = self._build_peer_comparison(company, ratios, benchmarks)
        comparison['explanation'] = selection_explanation
        comparison['peers'] = [pm.ticker for pm in peer_matches]
        
        return peer_matches, benchmarks, comparison
    
    def _build_peer_comparison(
        self,
        company: str,
        ratios: Dict[str, Any],
        benchmarks: PeerBenchmarks,
    ) -> Dict[str, Any]:
        """Build peer comparison for scoring adjustment."""
        comparisons = []
        
        # Use benchmarks data if available
        if benchmarks and benchmarks.benchmarks:
            for metric_name, benchmark in benchmarks.benchmarks.items():
                comparisons.append({
                    'metric': benchmark.metric_name,
                    'company_value': benchmark.company_value,
                    'peer_average': benchmark.peer_median,
                    'peer_median': benchmark.peer_median,
                    'position': benchmark.position,
                    'deviation_pct': benchmark.deviation_pct,
                    'percentile_rank': benchmark.percentile_rank,
                    'peers_compared': benchmark.peers_compared,
                })
        
        return {'comparisons': comparisons}
    
    def _detect_signals(
        self,
        company_data: Dict[str, Any],
        ratios: Dict[str, Any],
        sector: str,
        peer_benchmarks: Optional[PeerBenchmarks],
        current_year: int,
    ) -> List[Signal]:
        """Detect all forensic signals."""
        all_signals = []
        years = ratios.get('years', [])
        
        # Manipulation signals (with sector-aware filtering)
        manipulation_signals = self.manipulation_detector.detect_all(
            data=company_data,
            ratios=ratios,
            sector=sector,
        )
        all_signals.extend(manipulation_signals)
        
        # Stress signals
        stress_signals = self.stress_detector.detect_all(
            data=company_data,
            ratios=ratios,
            sector=sector,
        )
        all_signals.extend(stress_signals)
        
        # Bank-specific signals (if applicable)
        if sector in BANK_SECTORS:
            bank_signals = self.bank_detector.detect_all(
                data=company_data,
                ratios=ratios,
            )
            all_signals.extend(bank_signals)
        
        # Deduplicate signals by ID
        seen_ids = set()
        unique_signals = []
        for signal in all_signals:
            if signal.signal_id not in seen_ids:
                seen_ids.add(signal.signal_id)
                unique_signals.append(signal)
        
        return unique_signals
    
    def _analyze_sentiment(
        self,
        company: str,
        pdf_path: Optional[str],
        current_year: int,
    ) -> Dict[str, Any]:
        """Analyze auditor sentiment from cache, PDF, or return unavailable status."""
        # First, try cache-based analysis (fastest)
        cache_result = self.sentiment_analyzer.analyze_sentiment_trend(company)
        if cache_result.get('available'):
            self._log("Using cached auditor sentiment data")
            return cache_result
        
        # Second, try PDF-based analysis if available
        if pdf_path and self.pdf_parser:
            try:
                chunks = self.pdf_parser.parse(pdf_path)
                if chunks:
                    self.evidence_store.add_note_chunks(chunks)
                    result = self.sentiment_analyzer.analyze_real_notes(chunks, company)
                    if result.available:
                        return {
                            'available': True,
                            'is_real_data': True,
                            'trend': result,
                        }
            except Exception as e:
                self._log(f"PDF parsing failed: {e}")
        
        # No data available - return explicit unavailable status
        return {
            'available': False,
            'reason': cache_result.get('reason', 'No annual report PDF provided for real auditor note extraction'),
            'recommendation': cache_result.get('recommendation', 'Provide annual report PDF or create demo_qualitative_cache.json'),
            'is_real_data': False,
        }
    
    def _generate_report(
        self,
        result: AnalysisResult,
        company_data: Dict[str, Any],
        ratios: Dict[str, Any],
        peer_comparison: Dict[str, Any],
        sentiment_result: Dict[str, Any],
    ) -> Tuple[Dict[str, str], str, List[str]]:
        """Generate comprehensive forensic report."""
        missing_data = []
        
        # Generate each required section
        sections = {}
        
        # 0. Header
        sections['header'] = self.report_generator.generate_header(company_data)
        
        # 1. Executive Summary
        sections['executive_summary'] = self.report_generator.generate_executive_summary(
            dual_score=result.dual_score,
            signals=result.all_signals,
            sector=result.sector,
            company=result.company,
        )
        
        # 2. Manipulation/Fraud-Risk Signals
        sections['manipulation_signals'] = self.report_generator.generate_manipulation_signals_section(
            signals=result.all_signals,
        )
        
        # 3. Financial-Stress Signals
        sections['stress_signals'] = self.report_generator.generate_stress_signals_section(
            signals=result.all_signals,
        )
        
        # 4. Red-Flag Timeline
        sections['timeline'] = self.report_generator.generate_red_flag_timeline(
            signals=result.all_signals,
        )
        
        # 5. Auditor Note Trend
        if sentiment_result.get('available'):
            sections['auditor_sentiment'] = self.report_generator.generate_auditor_sentiment_section(
                sentiment_trend=sentiment_result.get('trend'),
                has_real_notes=sentiment_result.get('is_real_data', False),
            )
        else:
            sections['auditor_sentiment'] = (
                "\n" + "-" * 70 + "\n"
                "              AUDITOR NOTE SENTIMENT ANALYSIS\n" + "-" * 70 + "\n\n"
                f"  Data Status: UNAVAILABLE\n"
                f"  Reason: {sentiment_result.get('reason', 'No annual report PDF provided')}\n"
                f"  Recommendation: {sentiment_result.get('recommendation', 'Provide PDF for real analysis')}\n"
            )
            missing_data.append("Auditor sentiment analysis (no PDF provided)")
        
        # 6. Related-Party Trend
        rpt_available = ratios.get('other_income_pbt_ratio') is not None
        if rpt_available and not should_skip_rpt_proxy(result.sector):
            # Build RPT data
            rpt_data = self._build_rpt_data(company_data, ratios)
            sections['rpt_trend'] = self.report_generator.generate_rpt_section(
                rpt_data=rpt_data,
                has_real_rpt_notes=False,
                signals=result.all_signals,
            )
        else:
            sections['rpt_trend'] = (
                "\n" + "-" * 70 + "\n"
                "         RELATED PARTY TRANSACTION (RPT) ANALYSIS\n" + "-" * 70 + "\n\n"
                "  Data Status: UNAVAILABLE\n"
                "  Reason: Real RPT extraction from annual report notes not performed\n"
                "  Note: Other Income proxy disabled for this sector\n"
            )
            missing_data.append("Related-party transaction analysis (no PDF extraction)")
        
        # 7. Peer Selection Explanation
        peers_used = [pm.ticker for pm in result.peer_matches]
        sections['peer_selection'] = self.report_generator.generate_peer_explanation_section(
            peer_selection_explanation=peer_comparison.get('explanation', ''),
            peers_used=peers_used,
        )
        
        # 8. Peer Comparison Table
        sections['peer_comparison'] = self.report_generator.generate_peer_comparison_table(
            peer_comparison=peer_comparison,
        )
        
        # 9. Missing Data Disclosures
        # Update data availability based on sentiment analysis results
        data_availability = {
            'pnl': company_data.get('pnl') is not None,
            'balance_sheet': company_data.get('balance_sheet') is not None,
            'cash_flow': company_data.get('cash_flow') is not None,
            'auditor_notes': sentiment_result.get('available', False) or sentiment_result.get('is_cached', False),
            'rpt_notes': sentiment_result.get('has_rpt_notes', False),
        }
        
        # Track which data sources came from cache
        cached_sources = {
            'auditor_notes': sentiment_result.get('is_cached', False),
            'rpt_notes': sentiment_result.get('is_cached', False) and sentiment_result.get('has_rpt_notes', False),
        }
        
        # Remove items from missing_data if cache provided the data
        if data_availability['auditor_notes']:
            # Filter out auditor-related missing data entries
            missing_data = [
                item for item in missing_data 
                if 'auditor sentiment' not in item.lower()
            ]
        
        if data_availability['rpt_notes']:
            # Filter out RPT-related missing data entries
            missing_data = [
                item for item in missing_data 
                if 'related-party' not in item.lower() and 'rpt' not in item.lower()
            ]
        
        sections['missing_data'] = self.report_generator.generate_uncertainty_section(
            disclosures=missing_data,
            data_availability=data_availability,
            cached_sources=cached_sources,
        )
        
        # 10. Footer
        sections['footer'] = self.report_generator.generate_footer()
        
        # Combine into full report
        full_report = self.report_formatter.format_report(
            sections=sections,
            company=result.company,
            format_type=FormatType.PLAIN_TEXT,
        )
        
        return sections, full_report, missing_data
    
    def _build_rpt_data(self, company_data: Dict[str, Any], ratios: Dict[str, Any]) -> Dict[str, Dict]:
        """Build RPT data dict from company data."""
        rpt_data = {}
        
        pnl = company_data.get('pnl')
        if pnl is None:
            return rpt_data
        
        other_income_col = next((c for c in pnl.columns if 'Other Income' in c), None)
        revenue_col = ratios.get('revenue_col')
        
        if not other_income_col or not revenue_col or revenue_col not in pnl.columns:
            return rpt_data
        
        for year in pnl.index:
            oi = pnl.loc[year, other_income_col] if other_income_col in pnl.columns else 0
            rev = pnl.loc[year, revenue_col] if revenue_col in pnl.columns else 0
            ratio = (oi / rev * 100) if rev > 0 else 0
            
            rpt_data[year] = {
                'other_income': oi,
                'revenue': rev,
                'oi_to_revenue_pct': ratio,
            }
        
        return rpt_data
    
    def analyze_batch(
        self,
        companies: List[str],
        sector: Optional[str] = None,
    ) -> List[AnalysisResult]:
        """
        Analyze multiple companies in batch.
        
        Args:
            companies: List of company tickers
            sector: Optional sector override for all
            
        Returns:
            List of AnalysisResult objects
        """
        results = []
        for company in companies:
            self._log(f"Analyzing {company}...")
            result = self.analyze(company, sector=sector)
            results.append(result)
        return results
    
    def get_quick_score(self, company: str, sector: Optional[str] = None) -> DualScore:
        """
        Get quick dual score without full report generation.
        
        Useful for screening multiple companies quickly.
        """
        result = self.analyze(company, sector=sector)
        return result.dual_score


# Legacy compatibility function
def run_audit(
    company: str,
    sector: Optional[str] = None,
    verbose: bool = True,
) -> str:
    """
    Legacy entry point for backward compatibility.
    
    Returns the full report as a string.
    """
    engine = AuditGPT(verbose=verbose)
    result = engine.analyze(company, sector=sector)
    
    if result.success:
        return result.full_report
    else:
        return f"Analysis failed: {result.error_message}"
