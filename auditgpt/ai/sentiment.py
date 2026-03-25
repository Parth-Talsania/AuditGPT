"""
Real auditor sentiment analysis for AuditGPT.

Analyzes actual auditor note text for:
- Qualification language escalation
- Emphasis of matter
- Going concern warnings
- Material uncertainty mentions

IMPORTANT: If notes are unavailable, this module explicitly returns
"data unavailable" rather than fabricating analysis.
"""

from typing import List, Dict, Optional, Any
from collections import defaultdict
import re
import os
import json

from auditgpt.evidence.models import (
    NoteChunk, SentimentTrend, SentimentYear, EvidenceRef, RefType, SectionType
)
from auditgpt.config.constants import AUDITOR_RED_FLAG_WORDS, AUDITOR_STABLE_WORDS


# Exposed word lists for external use
RED_FLAG_WORDS = [
    'subject to', 'uncertainty', 'material misstatement', 'emphasis of matter',
    'except for', 'adverse', 'disclaimer', 'going concern', 'qualified opinion',
    'material weakness', 'significant deficiency', 'fraud', 'limitation of scope',
    'material uncertainty', 'unable to continue', 'significant doubt'
]

STABLE_WORDS = [
    'true and fair view', 'unmodified', 'compliance', 'unqualified',
    'clean opinion', 'fairly represents', 'in accordance with',
    'no material misstatement', 'properly maintained'
]


class AuditorSentimentAnalyzer:
    """
    Analyzes auditor note sentiment from annual reports.
    
    This is REAL sentiment analysis when actual note text is available.
    When notes are missing, it explicitly states unavailability.
    """
    
    # Critical escalation keywords (highest severity)
    CRITICAL_KEYWORDS = [
        'adverse opinion', 'disclaimer of opinion', 'disclaimer', 'fraud',
        'going concern', 'material uncertainty related to going concern',
        'significant doubt', 'unable to continue'
    ]
    
    # Warning keywords (high severity)
    WARNING_KEYWORDS = [
        'emphasis of matter', 'material uncertainty', 'qualified opinion',
        'except for', 'subject to', 'limitation of scope',
        'material weakness', 'significant deficiency'
    ]
    
    # Caution keywords (medium severity)
    CAUTION_KEYWORDS = [
        'key audit matter', 'audit matter', 'contingent liability',
        'pending litigation', 'regulatory matter', 'restatement',
        'prior period adjustment', 'deviation', 'non-compliance'
    ]
    
    # Stable/positive keywords
    STABLE_KEYWORDS = [
        'true and fair view', 'unmodified opinion', 'unqualified',
        'clean opinion', 'fairly represents', 'in accordance with',
        'no material misstatement', 'properly maintained'
    ]
    
    def __init__(self, cache_file: str = "demo_qualitative_cache.json"):
        self._compile_patterns()
        self.cache_file = cache_file
        self._qualitative_cache = None
        self._pdf_fetcher = None  # Lazy-loaded
    
    def _get_pdf_fetcher(self):
        """Lazy-load the PDF fetcher."""
        if self._pdf_fetcher is None:
            try:
                from auditgpt.ingestion.pdf_fetcher import AnnualReportFetcher
                self._pdf_fetcher = AnnualReportFetcher(
                    qualitative_cache_file=self.cache_file
                )
            except ImportError:
                pass
        return self._pdf_fetcher
    
    def _load_qualitative_cache(self) -> Optional[Dict[str, Any]]:
        """Load qualitative data cache if available."""
        if self._qualitative_cache is not None:
            return self._qualitative_cache
        
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, 'r') as f:
                    self._qualitative_cache = json.load(f)
                return self._qualitative_cache
            except (json.JSONDecodeError, IOError):
                pass
        return None
    
    def analyze_sentiment_trend(self, ticker: str) -> Dict[str, Any]:
        """
        Analyze auditor sentiment using tiered approach:
        
        Tier 1: Check qualitative cache (instant)
        Tier 2: Check local PDF directory (fast)
        Tier 3: Attempt BSE/Screener auto-fetch (slower but automated)
        Tier 4: Return unavailable with clear disclosure
        
        This provides the same flexibility as screener.in - works for any ticker.
        
        Args:
            ticker: Company ticker symbol
            
        Returns:
            Dict with sentiment analysis or unavailable status
        """
        ticker_upper = ticker.upper()
        
        # Tier 1: Check qualitative cache first (fastest)
        cache = self._load_qualitative_cache()
        if cache and ticker_upper in cache:
            ticker_data = cache[ticker_upper]
            result = self._analyze_cached_notes(ticker_upper, ticker_data)
            result['fetch_method'] = 'Tier 1: Qualitative Cache'
            return result
        
        # Tier 2-3: Use PDF fetcher for dynamic acquisition
        pdf_fetcher = self._get_pdf_fetcher()
        if pdf_fetcher:
            fetched = pdf_fetcher.fetch_notes(ticker_upper)
            
            if fetched.get('available'):
                # Convert to our analysis format
                ticker_data = {
                    'auditor_notes': fetched.get('auditor_notes', {}),
                    'rpt_notes': fetched.get('rpt_notes', {}),
                }
                result = self._analyze_cached_notes(ticker_upper, ticker_data)
                result['fetch_method'] = fetched.get('fetch_method', 'PDF Fetcher')
                result['source'] = fetched.get('source', 'dynamic')
                return result
            else:
                # Return with specific unavailability info
                return {
                    'available': False,
                    'is_real_data': False,
                    'fetch_method': fetched.get('fetch_method', 'Tier 4: Not Available'),
                    'reason': fetched.get('reason', f'No data available for {ticker}'),
                    'recommendation': fetched.get('recommendation', 
                        f'Add {ticker} to demo_qualitative_cache.json or provide annual report PDF'),
                }
        
        # Fallback: No cache and no PDF fetcher
        return {
            'available': False,
            'is_real_data': False,
            'fetch_method': 'Tier 4: Not Available',
            'reason': f'No cached data for {ticker} and PDF fetcher unavailable',
            'recommendation': f'Add {ticker} data to demo_qualitative_cache.json',
        }
    
    def _analyze_cached_notes(self, ticker: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze auditor notes from cached data."""
        auditor_notes = data.get('auditor_notes', {})
        rpt_notes = data.get('rpt_notes', {})
        
        if not auditor_notes:
            return {
                'available': False,
                'is_real_data': False,
                'reason': f'No auditor notes in cache for {ticker}',
            }
        
        # Create sentiment trend
        trend = SentimentTrend(available=True)
        years_analyzed = []
        
        for year_str, note_text in auditor_notes.items():
            try:
                year = int(year_str)
            except ValueError:
                continue
            
            # Count red flag words
            red_flag_count = sum(
                1 for word in RED_FLAG_WORDS
                if word.lower() in note_text.lower()
            )
            
            # Count stable words
            stable_count = sum(
                1 for word in STABLE_WORDS
                if word.lower() in note_text.lower()
            )
            
            # Calculate sentiment score
            score = (red_flag_count * 5) - (stable_count * 2)
            
            # Find specific keywords found
            keywords_found = [
                word for word in RED_FLAG_WORDS
                if word.lower() in note_text.lower()
            ]
            
            # Determine category
            if red_flag_count >= 3 or score >= 10:
                category = 'CRITICAL'
            elif red_flag_count >= 1 or score >= 3:
                category = 'CONCERNING'
            elif score >= 0:
                category = 'NEUTRAL'
            else:
                category = 'STABLE'
            
            sentiment_year = SentimentYear(
                year=year,
                score=score,
                category=category,
                red_flag_count=red_flag_count,
                stable_count=stable_count,
                hedged_keywords_found=keywords_found[:5],
                is_real_data=True,  # From cache = real data
                text_length=len(note_text),
            )
            
            trend.add_year(sentiment_year)
            years_analyzed.append(year)
        
        # Analyze trend patterns
        self._analyze_trend_patterns(trend)
        
        return {
            'available': True,
            'is_real_data': True,
            'is_cached': True,
            'trend': trend,
            'years_analyzed': sorted(years_analyzed),
            'has_rpt_notes': bool(rpt_notes),
            'rpt_data': rpt_notes,
        }
    
    def _compile_patterns(self):
        """Compile regex patterns for efficiency."""
        self._critical_pattern = re.compile(
            '|'.join(re.escape(k) for k in self.CRITICAL_KEYWORDS),
            re.IGNORECASE
        )
        self._warning_pattern = re.compile(
            '|'.join(re.escape(k) for k in self.WARNING_KEYWORDS),
            re.IGNORECASE
        )
        self._caution_pattern = re.compile(
            '|'.join(re.escape(k) for k in self.CAUTION_KEYWORDS),
            re.IGNORECASE
        )
        self._stable_pattern = re.compile(
            '|'.join(re.escape(k) for k in self.STABLE_KEYWORDS),
            re.IGNORECASE
        )
    
    def analyze_real_notes(
        self,
        note_chunks: List[NoteChunk],
        company: str,
    ) -> SentimentTrend:
        """
        Analyze REAL auditor notes extracted from annual reports.
        
        Args:
            note_chunks: List of NoteChunk objects from PDF parsing
            company: Company ticker/name
            
        Returns:
            SentimentTrend with real analysis or unavailable status
        """
        # Filter to auditor notes only
        auditor_notes = [
            chunk for chunk in note_chunks
            if chunk.section_type == SectionType.AUDITOR_NOTE
        ]
        
        if not auditor_notes:
            return SentimentTrend(
                available=False,
                reason="No auditor notes available. Annual report PDF parsing required."
            )
        
        # Group notes by year
        notes_by_year: Dict[int, List[NoteChunk]] = defaultdict(list)
        for chunk in auditor_notes:
            notes_by_year[chunk.filing_year].append(chunk)
        
        if not notes_by_year:
            return SentimentTrend(
                available=False,
                reason="No auditor notes found for any year."
            )
        
        # Analyze each year
        trend = SentimentTrend(available=True)
        
        for year, chunks in sorted(notes_by_year.items()):
            # Combine all text for the year
            combined_text = " ".join(chunk.text for chunk in chunks)
            
            # Analyze sentiment
            sentiment_year = self._analyze_year_text(year, combined_text, chunks[0])
            trend.add_year(sentiment_year)
        
        # Analyze trend patterns
        self._analyze_trend_patterns(trend)
        
        return trend
    
    def analyze_simulated_sentiment(
        self,
        anomalies: List[Dict[str, Any]],
        years: List[int],
    ) -> SentimentTrend:
        """
        Generate SIMULATED sentiment when real notes unavailable.
        
        IMPORTANT: This clearly marks data as simulated/proxy.
        Used only for demo purposes when PDF parsing not done.
        
        Args:
            anomalies: List of detected anomalies (for correlation)
            years: List of years to generate sentiment for
            
        Returns:
            SentimentTrend with simulated data (is_real_data=False)
        """
        trend = SentimentTrend(
            available=True,
            reason="Simulated from detected anomalies - actual notes not parsed"
        )
        
        # Build anomaly counts by year
        anomaly_by_year = defaultdict(lambda: {'critical': 0, 'high': 0, 'medium': 0})
        for a in anomalies:
            year = a.get('year')
            if year:
                severity = a.get('severity', 'LOW')
                if severity == 'CRITICAL':
                    anomaly_by_year[year]['critical'] += 1
                elif severity == 'HIGH':
                    anomaly_by_year[year]['high'] += 1
                elif severity == 'MEDIUM':
                    anomaly_by_year[year]['medium'] += 1
        
        for year in years:
            # Base score (simulated unqualified baseline)
            base_score = -2
            
            # Adjust based on anomalies
            year_data = anomaly_by_year.get(year, {'critical': 0, 'high': 0, 'medium': 0})
            score = base_score + (year_data['critical'] * 8) + (year_data['high'] * 4) + (year_data['medium'] * 1)
            
            # Determine category
            if score >= 10:
                category = 'CRITICAL'
                keywords = ['material uncertainty', 'going concern']
            elif score >= 5:
                category = 'CONCERNING'
                keywords = ['emphasis of matter', 'subject to']
            elif score >= 0:
                category = 'NEUTRAL'
                keywords = ['true and fair view']
            else:
                category = 'STABLE'
                keywords = ['unqualified', 'true and fair view']
            
            sentiment_year = SentimentYear(
                year=year,
                score=score,
                category=category,
                red_flag_count=year_data['critical'] + year_data['high'],
                stable_count=1 if category in ['STABLE', 'NEUTRAL'] else 0,
                hedged_keywords_found=keywords[:2] if score > 0 else [],
                is_real_data=False,  # Explicitly marked as simulated
                text_length=0,  # No actual text
            )
            
            trend.add_year(sentiment_year)
        
        return trend
    
    def _analyze_year_text(
        self,
        year: int,
        text: str,
        sample_chunk: NoteChunk,
    ) -> SentimentYear:
        """Analyze sentiment for a single year's text."""
        text_lower = text.lower()
        
        # Find keywords
        critical_matches = self._critical_pattern.findall(text_lower)
        warning_matches = self._warning_pattern.findall(text_lower)
        caution_matches = self._caution_pattern.findall(text_lower)
        stable_matches = self._stable_pattern.findall(text_lower)
        
        # Calculate score
        # Critical = +10, Warning = +5, Caution = +2, Stable = -2
        score = (
            len(critical_matches) * 10 +
            len(warning_matches) * 5 +
            len(caution_matches) * 2 -
            len(stable_matches) * 2
        )
        
        # All unique hedged keywords found
        hedged_keywords = list(set(
            critical_matches + warning_matches + caution_matches
        ))
        
        # Determine category
        if len(critical_matches) > 0 or score >= 10:
            category = 'CRITICAL'
        elif len(warning_matches) > 0 or score >= 5:
            category = 'CONCERNING'
        elif score >= 0:
            category = 'NEUTRAL'
        else:
            category = 'STABLE'
        
        # Create evidence reference
        evidence = EvidenceRef(
            ref_type=RefType.NOTE,
            filing_year=year,
            note_type=SectionType.AUDITOR_NOTE,
            page_number=sample_chunk.page_number,
            note_heading=sample_chunk.note_heading,
            snippet=text[:200] if text else None,
            source_file=sample_chunk.source_file,
        )
        
        return SentimentYear(
            year=year,
            score=score,
            category=category,
            red_flag_count=len(critical_matches) + len(warning_matches),
            stable_count=len(stable_matches),
            hedged_keywords_found=hedged_keywords[:5],
            evidence_ref=evidence,
            is_real_data=True,
            text_length=len(text),
        )
    
    def _analyze_trend_patterns(self, trend: SentimentTrend):
        """Analyze patterns in the sentiment trend."""
        years = trend.get_sorted_years()
        if len(years) < 2:
            return
        
        scores = [trend.years[y].score for y in years]
        
        # Check for deterioration streak
        streak = 0
        for i in range(1, len(scores)):
            if scores[i] > scores[i-1]:
                streak += 1
            else:
                streak = 0
        
        if streak >= 2:
            trend.is_deteriorating = True
            trend.deterioration_streak = streak
        
        # Check for spikes
        for i in range(1, len(years)):
            if scores[i] > scores[i-1] + 5:  # Significant jump
                trend.spike_years.append(years[i])
    
    def detect_sentiment_anomalies(
        self,
        trend: SentimentTrend,
    ) -> List[Dict[str, Any]]:
        """
        Detect anomalies in auditor sentiment.
        
        Returns list of anomaly dicts for integration with signal detection.
        """
        anomalies = []
        
        if not trend.available or len(trend.years) < 3:
            return anomalies
        
        years = trend.get_sorted_years()
        
        # Deterioration pattern
        if trend.is_deteriorating and trend.deterioration_streak >= 2:
            anomalies.append({
                'type': 'auditor_sentiment_deterioration',
                'year': years[-1],
                'severity': 'HIGH' if trend.deterioration_streak >= 3 else 'MEDIUM',
                'description': f"Auditor language becoming more hedged for {trend.deterioration_streak+1} consecutive years",
                'pattern': 'Auditor qualifications increasing - potential hidden issues',
                'is_real_data': all(trend.years[y].is_real_data for y in years[-3:]),
            })
        
        # Spike detection
        for spike_year in trend.spike_years:
            prev_year = spike_year - 1
            if prev_year in trend.years:
                prev_score = trend.years[prev_year].score
                curr_score = trend.years[spike_year].score
                
                anomalies.append({
                    'type': 'auditor_sentiment_spike',
                    'year': spike_year,
                    'severity': 'HIGH',
                    'description': f"Auditor hedging score jumped from {prev_score} to {curr_score}",
                    'pattern': 'Sudden increase in qualified language - investigate cause',
                    'is_real_data': trend.years[spike_year].is_real_data,
                })
        
        return anomalies
