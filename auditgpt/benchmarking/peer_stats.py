"""
Robust peer statistics for AuditGPT.

Uses robust statistical methods:
- Median instead of mean
- IQR (Interquartile Range) for outlier detection
- MAD (Median Absolute Deviation) for dispersion
- Percentile ranking for comparison
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple
import numpy as np


@dataclass
class MetricBenchmark:
    """Benchmark statistics for a single metric."""
    
    metric_name: str
    company_value: float
    
    # Robust stats
    peer_median: float
    peer_q1: float  # 25th percentile
    peer_q3: float  # 75th percentile
    peer_iqr: float  # Q3 - Q1
    peer_mad: float  # Median Absolute Deviation
    peer_min: float
    peer_max: float
    
    # Position
    percentile_rank: float  # Where company sits (0-100)
    position: str  # 'ABOVE', 'BELOW', 'BETTER', 'WORSE', 'AT_MEDIAN'
    deviation_from_median: float  # Company value - median
    deviation_pct: float  # % deviation from median
    
    # Context
    higher_is_better: bool = True
    peers_compared: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'metric_name': self.metric_name,
            'company_value': self.company_value,
            'peer_median': self.peer_median,
            'peer_q1': self.peer_q1,
            'peer_q3': self.peer_q3,
            'peer_iqr': self.peer_iqr,
            'peer_mad': self.peer_mad,
            'peer_min': self.peer_min,
            'peer_max': self.peer_max,
            'percentile_rank': self.percentile_rank,
            'position': self.position,
            'deviation_from_median': self.deviation_from_median,
            'deviation_pct': self.deviation_pct,
            'higher_is_better': self.higher_is_better,
            'peers_compared': self.peers_compared,
        }
    
    @property
    def is_outlier(self) -> bool:
        """Check if company value is an outlier (beyond 1.5 IQR)."""
        lower_bound = self.peer_q1 - 1.5 * self.peer_iqr
        upper_bound = self.peer_q3 + 1.5 * self.peer_iqr
        return self.company_value < lower_bound or self.company_value > upper_bound
    
    @property
    def outlier_direction(self) -> Optional[str]:
        """Get direction of outlier if applicable."""
        if not self.is_outlier:
            return None
        if self.company_value < self.peer_q1 - 1.5 * self.peer_iqr:
            return 'LOW_OUTLIER'
        return 'HIGH_OUTLIER'


@dataclass
class PeerBenchmarks:
    """Complete peer benchmark results."""
    
    company_ticker: str
    sector: str
    peers_used: List[str]
    year: int
    
    benchmarks: Dict[str, MetricBenchmark] = field(default_factory=dict)
    
    # Summary
    above_median_count: int = 0
    below_median_count: int = 0
    outlier_count: int = 0
    
    def add_benchmark(self, benchmark: MetricBenchmark):
        """Add a metric benchmark."""
        self.benchmarks[benchmark.metric_name] = benchmark
        
        # Update summary counts
        if benchmark.position in ['ABOVE', 'BETTER']:
            self.above_median_count += 1
        elif benchmark.position in ['BELOW', 'WORSE']:
            self.below_median_count += 1
        
        if benchmark.is_outlier:
            self.outlier_count += 1
    
    def get_comparison_table(self) -> List[Dict[str, Any]]:
        """Get data for peer comparison table."""
        return [bm.to_dict() for bm in self.benchmarks.values()]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'company_ticker': self.company_ticker,
            'sector': self.sector,
            'peers_used': self.peers_used,
            'year': self.year,
            'benchmarks': {k: v.to_dict() for k, v in self.benchmarks.items()},
            'above_median_count': self.above_median_count,
            'below_median_count': self.below_median_count,
            'outlier_count': self.outlier_count,
        }


class PeerStats:
    """
    Calculates robust statistics for peer comparison.
    
    Uses robust methods that are less sensitive to outliers:
    - Median instead of mean
    - MAD instead of standard deviation
    - IQR-based outlier detection
    """
    
    # Metrics and whether higher is better
    # Maps internal keys to display names and alternate key names
    METRIC_CONFIG = {
        'revenue_growth': {'display': 'Revenue Growth', 'higher_better': True, 'alt_keys': ['revenue_growth']},
        'profit_growth': {'display': 'Profit Growth', 'higher_better': True, 'alt_keys': ['profit_growth', 'np_growth']},
        'opm': {'display': 'Operating Margin', 'higher_better': True, 'alt_keys': ['opm', 'opm_']},
        'roce': {'display': 'ROCE', 'higher_better': True, 'alt_keys': ['roce_', 'roce', 'roe_', 'roe']},
        'debt_equity': {'display': 'Debt/Equity', 'higher_better': False, 'alt_keys': ['debt_equity']},
        'debtor_days': {'display': 'Debtor Days', 'higher_better': False, 'alt_keys': ['debtor_days']},
    }
    
    METRIC_DIRECTION = {
        'revenue_growth': True,
        'profit_growth': True,
        'np_growth': True,
        'opm': True,
        'roce_': True,
        'roce': True,
        'roe': True,
        'roe_': True,
        'current_ratio': True,
        'debt_equity': False,  # Lower is better
        'debtor_days': False,
        'working_capital_days': False,
        'npa': False,  # Lower is better
        'gnpa': False,
        'nnpa': False,
        'car': True,  # Higher is better
    }
    
    def compute_benchmarks(
        self,
        company_ticker: str,
        company_ratios: Dict[str, Any],
        peer_ratios: Dict[str, Dict[str, Any]],
        sector: str,
        year: Optional[int] = None,
    ) -> PeerBenchmarks:
        """
        Compute comprehensive peer benchmarks.
        
        Args:
            company_ticker: Target company ticker
            company_ratios: Target company ratios
            peer_ratios: Dict mapping peer tickers to their ratios
            sector: Company sector
            year: Year for comparison (latest if None)
            
        Returns:
            PeerBenchmarks with all comparisons
        """
        # Determine year
        if year is None:
            year = self._get_latest_year(company_ratios)
        
        benchmarks = PeerBenchmarks(
            company_ticker=company_ticker,
            sector=sector,
            peers_used=list(peer_ratios.keys()),
            year=year,
        )
        
        # Use METRIC_CONFIG for standardized comparison
        for metric_key, config in self.METRIC_CONFIG.items():
            benchmark = self._compute_metric_benchmark_flexible(
                metric_key=metric_key,
                metric_name=config['display'],
                alt_keys=config['alt_keys'],
                higher_better=config['higher_better'],
                company_ratios=company_ratios,
                peer_ratios=peer_ratios,
                year=year,
            )
            
            if benchmark:
                benchmarks.add_benchmark(benchmark)
        
        return benchmarks
    
    def _compute_metric_benchmark_flexible(
        self,
        metric_key: str,
        metric_name: str,
        alt_keys: List[str],
        higher_better: bool,
        company_ratios: Dict[str, Any],
        peer_ratios: Dict[str, Dict[str, Any]],
        year: int,
    ) -> Optional[MetricBenchmark]:
        """Compute benchmark for a single metric with flexible key matching."""
        # Try to get company value using alternate keys
        company_value = None
        used_key = None
        
        for key in alt_keys:
            data = company_ratios.get(key)
            if data is not None:
                company_value = self._extract_value(data, year, company_ratios)
                if company_value is not None:
                    used_key = key
                    break
        
        if company_value is None:
            return None
        
        # Get peer values
        peer_values = []
        peers_used = []
        
        for peer_ticker, ratios in peer_ratios.items():
            peer_val = None
            for key in alt_keys:
                data = ratios.get(key)
                if data is not None:
                    peer_val = self._extract_value(data, year, ratios)
                    if peer_val is not None:
                        break
            
            if peer_val is not None:
                peer_values.append(peer_val)
                peers_used.append(peer_ticker)
        
        if len(peer_values) < 2:
            return None  # Not enough peers for meaningful comparison
        
        # Calculate robust statistics
        peer_array = np.array(peer_values)
        
        median = np.median(peer_array)
        q1 = np.percentile(peer_array, 25)
        q3 = np.percentile(peer_array, 75)
        iqr = q3 - q1
        mad = np.median(np.abs(peer_array - median))
        
        # Calculate percentile rank
        percentile = (np.sum(peer_array < company_value) / len(peer_array)) * 100
        
        # Determine position
        if mad > 0 and abs(company_value - median) < mad * 0.5:
            position = 'AT_MEDIAN'
        elif company_value > median:
            position = 'ABOVE' if higher_better else 'WORSE'
        else:
            position = 'BELOW' if higher_better else 'BETTER'
        
        # Calculate deviation
        deviation = company_value - median
        deviation_pct = (deviation / abs(median) * 100) if median != 0 else 0
        
        return MetricBenchmark(
            metric_name=metric_name,
            company_value=company_value,
            peer_median=median,
            peer_q1=q1,
            peer_q3=q3,
            peer_iqr=iqr,
            peer_mad=mad,
            peer_min=np.min(peer_array),
            peer_max=np.max(peer_array),
            percentile_rank=percentile,
            position=position,
            deviation_from_median=deviation,
            deviation_pct=deviation_pct,
            higher_is_better=higher_better,
            peers_compared=peers_used,
        )
    
    def _extract_value(self, data: Any, year: int, ratios: Dict[str, Any]) -> Optional[float]:
        """Extract a numeric value from various data formats."""
        if data is None:
            return None
        
        # If it's a list, use index based on years
        if isinstance(data, list):
            years = ratios.get('years', [])
            if years and len(data) == len(years):
                try:
                    idx = years.index(str(year)) if str(year) in years else years.index(year)
                    return data[idx] if idx < len(data) else None
                except (ValueError, IndexError):
                    pass
            # Fallback: return last value
            if data:
                val = data[-1]
                return val if val is not None and not (isinstance(val, float) and np.isnan(val)) else None
            return None
        
        # If it's a dict with year keys
        if isinstance(data, dict):
            val = data.get(str(year)) or data.get(year)
            if val is not None:
                return val
            # Fallback: return latest available value
            if data:
                for k in sorted(data.keys(), reverse=True):
                    v = data[k]
                    if v is not None and not (isinstance(v, float) and np.isnan(v)):
                        return v
            return None
        
        # If it's a single number
        if isinstance(data, (int, float)):
            return data if not np.isnan(data) else None
        
        return None
    
    def _get_latest_year(self, ratios: Dict[str, Any]) -> int:
        """Get the latest year from ratios data."""
        for key, value in ratios.items():
            if isinstance(value, dict) and value:
                years = [int(y) for y in value.keys() if str(y).isdigit()]
                if years:
                    return max(years)
        return 2025  # Default
    
    def compute_zscore(
        self,
        company_value: float,
        peer_values: List[float]
    ) -> Tuple[float, str]:
        """
        Compute robust z-score using MAD.
        
        Args:
            company_value: Company's metric value
            peer_values: List of peer values
            
        Returns:
            Tuple of (z-score, interpretation)
        """
        if not peer_values:
            return 0, "No peers for comparison"
        
        peer_array = np.array(peer_values)
        median = np.median(peer_array)
        mad = np.median(np.abs(peer_array - median))
        
        if mad == 0:
            return 0, "No variation among peers"
        
        # Modified z-score using MAD
        z_score = 0.6745 * (company_value - median) / mad
        
        # Interpretation
        if abs(z_score) < 1:
            interpretation = "Within normal range"
        elif abs(z_score) < 2:
            interpretation = "Moderately different from peers"
        elif abs(z_score) < 3:
            interpretation = "Significantly different from peers"
        else:
            interpretation = "Extreme outlier vs peers"
        
        return z_score, interpretation
