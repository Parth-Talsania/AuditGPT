# AuditGPT Forensic Engine Refactor

## Current State Analysis

**Existing `audit_gpt.py` (1976 lines):**
- Monolithic structure with 9 classes in one file
- `DataAcquisition`: Scrapes screener.in for structured financials
- `AuditorSentimentAnalyzer`: Has RED_FLAG_WORDS but uses **mock sentiment** (line 1786-1846)
- `AnomalyDetector`: Rule-based with structural break detection, bank-specific NPA checks
- `FraudRiskScorer`: Sigmoid scoring with recency weighting
- **Critical Issues:**
  - Line 1904: `_generate_mock_auditor_sentiment()` - fabricates sentiment from anomaly counts
  - Line 1095-1168: Uses "Other Income" as RPT proxy - explicitly disallowed for banks
  - Single fraud score - no separation of manipulation vs financial-stress
  - Static peer groups in `PEER_GROUPS` dict (line 124-131)
  - No real PDF parsing or evidence citations

---

## PHASE A: Modular Package Structure

### A1. Create Directory Structure
```
auditgpt/
├── __init__.py
├── config/
│   ├── __init__.py
│   ├── constants.py          # FRAUD_PATTERNS, INDUSTRY_NORMS, SECTOR_MAPPING
│   └── thresholds.py         # Sector-specific threshold configs
├── ingestion/
│   ├── __init__.py
│   ├── screener.py           # DataAcquisition class
│   ├── csv_loader.py         # Load cached CSVs
│   └── cache.py              # Caching layer with TTL
├── extraction/
│   ├── __init__.py
│   ├── pdf_parser.py         # PyMuPDF/pdfplumber hybrid parser
│   ├── section_detector.py   # Detect auditor/RPT/MD&A sections
│   └── note_normalizer.py    # Map headings to canonical types
├── evidence/
│   ├── __init__.py
│   ├── models.py             # Evidence, NoteChunk, StatementRef dataclasses
│   └── store.py              # Evidence storage and retrieval
├── ai/
│   ├── __init__.py
│   ├── embeddings.py         # Sentence embeddings for retrieval
│   ├── retriever.py          # Hybrid lexical + semantic RAG
│   ├── section_classifier.py # Classify note chunks
│   ├── sentiment.py          # Real auditor sentiment analysis
│   └── report_generator.py   # LLM-grounded explanation generation
├── benchmarking/
│   ├── __init__.py
│   ├── peer_selector.py      # Dynamic peer selection engine
│   └── peer_stats.py         # Robust stats (median, IQR, MAD)
├── signals/
│   ├── __init__.py
│   ├── base.py               # Signal dataclass with evidence refs
│   ├── manipulation.py       # Fraud-risk signals
│   ├── stress.py             # Financial-stress signals
│   └── bank_specific.py      # Bank/NBFC asset quality signals
├── scoring/
│   ├── __init__.py
│   ├── dual_scorer.py        # Separate manipulation + stress scores
│   └── confidence.py         # Confidence calibration
├── reporting/
│   ├── __init__.py
│   ├── sections.py           # Report section generators
│   └── formatter.py          # Plain-text and JSON output
├── api/
│   ├── __init__.py
│   └── engine.py             # Main AuditGPT facade
└── tests/
    ├── __init__.py
    ├── conftest.py
    ├── fixtures/             # Test data for regression
    ├── test_signals.py
    ├── test_scoring.py
    ├── test_evidence.py
    └── test_banking.py
```

### A2. Create Project Rules
**File: `.qoder/rules/audit_rules.md`**
- Evidence-first: Every signal must reference source
- Benchmark-first: All thresholds sector/peer-aware
- No fabrication: Explicit "data unavailable" if missing
- Bank separation: stress vs manipulation mandatory
- Deterministic math: AI only for NLP/retrieval/explanation
- Sub-90s goal: Caching at every layer

**File: `AGENTS.md`**
- Document module responsibilities and contracts

---

## PHASE B: PDF Parsing for Real Note Extraction

### B1. Hybrid PDF Parser (`extraction/pdf_parser.py`)
```python
class PDFParser:
    def parse(self, pdf_path: str) -> List[NoteChunk]:
        # Primary: PyMuPDF text extraction
        # Fallback: pytesseract OCR for scanned pages
        # Returns list of NoteChunk with metadata
```

**NoteChunk dataclass (`evidence/models.py`):**
```python
@dataclass
class NoteChunk:
    company: str
    filing_year: int
    source_file: str
    page_number: int
    note_heading: Optional[str]
    note_number: Optional[str]
    paragraph_index: int
    text: str
    section_type: Literal['auditor_note', 'related_party', 'mda', 'risk', 'other']
```

### B2. Section Detection (`extraction/section_detector.py`)
Pattern matching for:
- **Auditor sections:** "Independent Auditor's Report", "Basis for Opinion", "Emphasis of Matter", "Key Audit Matters", "Going Concern"
- **RPT sections:** "Related Party Transactions", "Note XX - Related Party", "Transactions with Related Parties"
- **MD&A:** "Management Discussion and Analysis", "Business Overview", "Risk Factors"

### B3. Heading Normalization (`extraction/note_normalizer.py`)
Map variant headings to canonical section types:
```python
AUDITOR_PATTERNS = [
    r"independent\s*auditor", r"basis\s*for\s*opinion",
    r"emphasis\s*of\s*matter", r"key\s*audit\s*matter",
    r"going\s*concern", r"material\s*uncertainty"
]
```

---

## PHASE C: Evidence Model and Citations

### C1. Evidence Schema (`evidence/models.py`)
```python
@dataclass
class EvidenceRef:
    ref_type: Literal['statement', 'note', 'ratio']
    filing_year: int
    # For statement refs:
    statement_type: Optional[str]  # 'P&L', 'Balance Sheet', 'Cash Flow'
    line_item: Optional[str]
    # For note refs:
    note_type: Optional[str]       # 'auditor_note', 'related_party', 'mda'
    page_number: Optional[int]
    note_number: Optional[str]
    paragraph_index: Optional[int]
    snippet: Optional[str]         # Max 200 chars of actual text
    
    @property
    def citation_string(self) -> str:
        if self.ref_type == 'statement':
            return f"{self.statement_type} > {self.line_item} > FY{self.filing_year}"
        elif self.ref_type == 'note':
            parts = [f"Annual Report FY{self.filing_year}"]
            if self.page_number:
                parts.append(f"Page {self.page_number}")
            if self.note_number:
                parts.append(f"Note {self.note_number}")
            return " > ".join(parts)
```

### C2. Evidence Store (`evidence/store.py`)
```python
class EvidenceStore:
    def add_note_chunks(self, chunks: List[NoteChunk])
    def get_notes_by_company_year(self, company: str, year: int) -> List[NoteChunk]
    def get_notes_by_section_type(self, section_type: str) -> List[NoteChunk]
    def search_notes(self, query: str) -> List[NoteChunk]  # For RAG
```

---

## PHASE D: Real AI/GenAI/RAG Layer

### D1. Section Classifier (`ai/section_classifier.py`)
Use small transformer or keyword rules to classify extracted chunks:
```python
class SectionClassifier:
    def classify(self, text: str) -> str:
        # Returns: 'auditor_note', 'related_party', 'mda', 'risk', 'other'
        # Primary: keyword + regex patterns
        # Optional: sentence-transformers for ambiguous cases
```

### D2. Hybrid Retriever (`ai/retriever.py`)
```python
class HybridRetriever:
    def __init__(self, evidence_store: EvidenceStore):
        self.lexical = BM25Retriever()      # Fast keyword matching
        self.semantic = EmbeddingRetriever() # sentence-transformers
    
    def retrieve(self, query: str, top_k: int = 5) -> List[NoteChunk]:
        # Reciprocal rank fusion of lexical + semantic results
```

### D3. Real Auditor Sentiment (`ai/sentiment.py`)
```python
class AuditorSentimentAnalyzer:
    ESCALATION_KEYWORDS = {
        'critical': ['adverse opinion', 'disclaimer', 'going concern', 'fraud'],
        'warning': ['emphasis of matter', 'material uncertainty', 'qualified', 'except for'],
        'caution': ['key audit matter', 'subject to', 'limitation']
    }
    
    def analyze_real_notes(self, notes: List[NoteChunk]) -> SentimentTrend:
        # Analyze actual extracted text, not mocked
        # Return yearly scores with evidence refs
        # If notes unavailable: return SentimentTrend(available=False, reason="...")
```

### D4. Grounded Report Generator (`ai/report_generator.py`)
```python
class GroundedReportGenerator:
    def generate_explanation(self, signal: Signal, evidence: List[EvidenceRef]) -> str:
        # Use LLM (optional) with strict grounding prompt
        # Fallback: template-based generation from signal + evidence
        # NEVER generate claims without evidence refs
```

---

## PHASE E: Cross-Statement Anomaly Engine Upgrade

### E1. Signal Base Class (`signals/base.py`)
```python
@dataclass
class Signal:
    signal_id: str
    signal_family: str              # 'revenue_divergence', 'npa_spike', etc.
    manipulation_or_stress: Literal['manipulation', 'stress', 'both']
    year_first_seen: int
    current_severity: Literal['CRITICAL', 'HIGH', 'MEDIUM', 'LOW']
    company_history_comparison: str  # "3σ above historical mean"
    peer_comparison: Optional[str]   # "Worst in peer group"
    evidence_refs: List[EvidenceRef]
    confidence: float               # 0.0 to 1.0
    explanation_seed: str           # Template for report text
```

### E2. Manipulation Signals (`signals/manipulation.py`)
- `RevenueVsCFODivergence`: **Fix** non-positive CFO baseline handling
- `PersistentProfitQualityIssue`: CFO/NP ratio < 0.5 for 3+ years
- `ReceivablesSpike`: Debtor days > 1.5x peer median
- `UnusualRPTGrowth`: **Only if real RPT note extraction available**
- `AuditorLanguageEscalation`: Based on real note sentiment trend
- `DisclosureComplexityIncrease`: Note length/complexity growth
- `OneTimeGainDependence`: Other income > 20% of PBT (sector-filtered)

### E3. Financial Stress Signals (`signals/stress.py`)
- `LeverageStress`: D/E > 2x sector norm
- `InterestCoverageDeterioration`: ICR < 2 or declining
- `LiquidityPressure`: Current ratio < 1.0
- `CapitalAdequacyWeakness`: CAR < 12% (banks)
- `GNPAStress`: GNPA spike or > 5% (banks)
- `NNPAStress`: NNPA > 3% (banks)
- `ProvisioningStress`: Provisions/GNPA declining (banks)
- `ProfitabilityCollapse`: NP margin < 0 or > 50% decline
- `WeakCFOGeneration`: CFO < 0 for 2+ consecutive years
- `WorseningROCE`: Declining for 3+ years below sector min

### E4. Bug Fixes
- **Line 651-655**: Fix CFO growth when `cfo_vals[0] <= 0`:
  ```python
  if cfo_vals[0] <= 0:
      # Skip comparison instead of -100% growth
      continue
  ```
- **Line 969-978**: Deduplicate `bank_loss` + `bank_profit_collapse` for same year
- **Line 1095-1168**: Disable Other Income as RPT proxy for BANK/FINANCE:
  ```python
  if sector in ('BANK', 'FINANCE'):
      return []  # Skip proxy RPT for banks
  ```
- **Line 543-572**: Add confidence to structural break detection, avoid overclaiming M&A

---

## PHASE F: Real Peer Selection Layer

### F1. Dynamic Peer Selector (`benchmarking/peer_selector.py`)
```python
class PeerSelector:
    def select_peers(self, company: CompanyData, min_peers: int = 5) -> List[PeerMatch]:
        # 1. Filter by sector (BANK, IT, PHARMA, etc.)
        # 2. Filter by sub-industry where available
        # 3. Size filter: 0.3x - 3x revenue/assets
        # 4. Optional: embedding similarity on business descriptions
        # 5. Explain selection reasoning for each peer
        
    def get_peer_universe(self, sector: str) -> List[str]:
        # Separate universes:
        # - Private Banks: HDFC, ICICI, AXIS, KOTAK, INDUSIND
        # - PSU Banks: SBI, PNB, BOB, CANARA, UNION
        # - NBFCs: BAJFINANCE, MUTHOOTFIN, CHOLAFIN
        # - IT Services: TCS, INFY, WIPRO, HCLTECH, TECHM, LTIM
        # - Realty: DLF, GODREJPROP, OBEROI, PRESTIGE (NOT infra)
```

### F2. Robust Statistics (`benchmarking/peer_stats.py`)
```python
class PeerStats:
    def compute_benchmarks(self, peer_data: Dict[str, RatioSet]) -> PeerBenchmarks:
        # Use median, not mean
        # Compute IQR for outlier detection
        # MAD (median absolute deviation) for robust comparison
        # Return position: percentile rank in peer group
```

---

## PHASE G: Dual-Score Output and Report Redesign

### G1. Dual Scorer (`scoring/dual_scorer.py`)
```python
class DualScorer:
    def score(self, signals: List[Signal], peer_comparison: PeerComparison) -> DualScore:
        manipulation_signals = [s for s in signals if s.manipulation_or_stress in ('manipulation', 'both')]
        stress_signals = [s for s in signals if s.manipulation_or_stress in ('stress', 'both')]
        
        manipulation_score = self._compute_score(manipulation_signals)
        stress_score = self._compute_score(stress_signals)
        combined_score = 0.6 * manipulation_score + 0.4 * stress_score
        
        return DualScore(
            manipulation_score=manipulation_score,
            manipulation_level=self._get_level(manipulation_score),
            stress_score=stress_score,
            stress_level=self._get_level(stress_score),
            combined_score=combined_score,
            combined_level=self._get_level(combined_score)
        )
```

### G2. Report Sections (`reporting/sections.py`)
Required sections:
1. **Executive Summary**: One-paragraph with dual scores
2. **Manipulation/Fraud-Risk Signals**: With evidence citations
3. **Financial-Stress/Asset-Quality Signals**: Separated for clarity
4. **Red-Flag Timeline**: Year-by-year with source refs
5. **Auditor Note Trend**: Real citations or explicit "unavailable"
6. **Related-Party Trend**: Real citations or explicit "proxy only"
7. **Peer Selection Explanation**: Why each peer was chosen
8. **Peer Comparison Table**: Company vs peer median/percentiles
9. **Uncertainty/Missing-Data Disclosures**: What analysis couldn't be done

---

## PHASE H: Testing and Regression Safety

### H1. Test Structure
```
tests/
├── fixtures/
│   ├── healthy_it_company.json      # e.g., TCS
│   ├── stressed_bank.json           # e.g., YESBANK
│   ├── realty_case.json             # e.g., DLF
│   ├── negative_cfo_company.json    # Company with unstable CFO
│   └── partial_notes.json           # Missing annual report data
├── test_manipulation_signals.py
├── test_stress_signals.py
├── test_bank_specific.py
├── test_peer_selection.py
├── test_evidence_integrity.py
├── test_score_regression.py
└── test_report_grounding.py
```

### H2. Key Test Cases
- **Score regression**: YESBANK should score CRITICAL, TCS should score LOW
- **Bank separation**: PNB stress signals should dominate over manipulation
- **Evidence integrity**: Every signal has at least one evidence ref
- **No fabrication**: Report text doesn't claim citations that don't exist
- **CFO edge cases**: Handle negative CFO without bogus -100% growth

---

## PHASE I: Performance and Demo Readiness

### I1. Caching Strategy
```python
class CacheManager:
    def __init__(self, cache_dir: str = ".cache/auditgpt"):
        self.statement_cache = TTLCache(maxsize=100, ttl=3600)
        self.note_cache = TTLCache(maxsize=50, ttl=86400)
        self.peer_cache = TTLCache(maxsize=20, ttl=1800)
```

### I2. Timing Instrumentation
```python
@dataclass
class AnalysisTiming:
    data_fetch_ms: int
    ratio_calc_ms: int
    anomaly_detection_ms: int
    peer_benchmark_ms: int
    report_generation_ms: int
    total_ms: int
```

### I3. Progressive Output
- Return preliminary score + key signals within 30s
- Full report with all sections within 90s
- Optional chart generation deferred/lazy

---

## Implementation Order

1. **Phase A** (2-3 hours): Create package structure, move constants, create base classes
2. **Phase C** (1 hour): Evidence models (needed by other phases)
3. **Phase E** (2-3 hours): Fix anomaly bugs, create signal classes with evidence refs
4. **Phase G** (2 hours): Dual scorer and report sections
5. **Phase F** (1.5 hours): Peer selector with robust stats
6. **Phase H** (2 hours): Core tests
7. **Phase B** (2-3 hours): PDF parsing (can proceed in parallel with optional flag)
8. **Phase D** (2-3 hours): RAG layer (builds on Phase B)
9. **Phase I** (1 hour): Caching and timing

**Total estimated: 16-20 hours of implementation**

---

## Backward Compatibility

Preserve `audit_gpt.py` entrypoint:
```python
# audit_gpt.py (updated)
from auditgpt.api.engine import AuditGPT

if __name__ == "__main__":
    engine = AuditGPT()
    # ... existing main code
```

---

## Known Limitations (Post-Implementation)

1. PDF parsing requires actual annual report PDFs (not fetched automatically)
2. RAG embeddings need sentence-transformers model (~500MB)
3. LLM-based explanations optional (falls back to templates)
4. Real-time demo relies on cached peer data for speed
5. NBFC-specific signals not as developed as bank signals