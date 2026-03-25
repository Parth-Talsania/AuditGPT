# AuditGPT Module Contracts

This document defines the responsibilities and contracts for each module in the AuditGPT forensic analysis engine.

## Core Principles

1. **Evidence-First**: Every signal MUST reference its source (statement line item, note page, ratio calculation)
2. **Benchmark-First**: All thresholds are sector-aware and peer-relative
3. **No Fabrication**: When data is unavailable, explicitly state "data unavailable" - never generate mock data
4. **Bank Separation**: For bank/NBFC sectors, ALWAYS separate stress signals from manipulation signals
5. **Deterministic Math**: AI is only used for NLP, retrieval, and explanation generation - not scoring
6. **Performance Goal**: Complete analysis in under 90 seconds with caching

---

## Module Responsibilities

### `auditgpt.config`
**Purpose**: Centralized configuration and thresholds

- `constants.py`: Industry norms, sector mappings, peer groups, severity weights
- `thresholds.py`: Sector-specific threshold configurations

**Contracts**:
- MUST NOT contain any business logic
- MUST export `should_skip_cfo_analysis(sector)` and `should_skip_rpt_proxy(sector)`
- All constants are immutable at runtime

---

### `auditgpt.ingestion`
**Purpose**: Data acquisition from external sources

- `screener.py`: Scrapes screener.in for financial statements
- `csv_loader.py`: Loads cached CSV data
- `cache.py`: TTL-based caching layer

**Contracts**:
- MUST implement retry logic for network failures
- MUST normalize data format across sources
- MUST support cache invalidation

---

### `auditgpt.extraction`
**Purpose**: PDF parsing and note extraction

- `pdf_parser.py`: Hybrid PyMuPDF + OCR parser
- `section_detector.py`: Detect auditor/RPT/MD&A sections
- `note_normalizer.py`: Map headings to canonical types

**Contracts**:
- MUST return `NoteChunk` objects with page numbers
- MUST handle both text-based and scanned PDFs
- MUST NOT generate fake note content

---

### `auditgpt.evidence`
**Purpose**: Evidence tracking and citation

- `models.py`: `EvidenceRef`, `NoteChunk`, `RefType` dataclasses
- `store.py`: Evidence storage and retrieval

**Contracts**:
- Every `EvidenceRef` MUST have a valid `citation_string` property
- Store MUST support query by company, year, and section type

---

### `auditgpt.signals`
**Purpose**: Signal detection and classification

- `base.py`: `Signal` dataclass with severity, category, evidence refs
- `manipulation.py`: Fraud-risk signals (CFO divergence, quality issues)
- `stress.py`: Financial stress signals (leverage, liquidity)
- `bank_specific.py`: NPA, CAR, provisioning signals

**Contracts**:
- Every signal MUST have at least one `EvidenceRef`
- MUST classify as `MANIPULATION`, `STRESS`, or `BOTH`
- MUST set `is_real_data` flag appropriately
- CFO analysis: Skip if baseline <= 0 (no bogus -100% growth)
- Bank signals: Deduplicate loss + collapse for same year

---

### `auditgpt.scoring`
**Purpose**: Dual scoring with Forensic Sigmoid

- `dual_scorer.py`: Separate manipulation and stress scores

**Contracts**:
- MUST output `DualScore` with both scores
- Base risk of 8-10 (no company is perfect)
- Score range: 8 to 95 (avoid 0/100 extremes)
- Combined = 0.6 * manipulation + 0.4 * stress

---

### `auditgpt.benchmarking`
**Purpose**: Dynamic peer selection and statistics

- `peer_selector.py`: Select comparable companies
- `peer_stats.py`: Robust statistics (median, IQR, MAD)

**Contracts**:
- MUST filter by sector and size (0.3x to 3x revenue)
- MUST explain selection reasoning for each peer
- MUST use median, not mean, for comparisons

---

### `auditgpt.ai`
**Purpose**: NLP and retrieval components

- `sentiment.py`: Auditor sentiment analysis
- `retriever.py`: Hybrid BM25 + semantic retrieval
- `section_classifier.py`: Classify note sections

**Contracts**:
- MUST distinguish real vs simulated analysis
- `analyze_real_notes()` for actual PDF content
- `analyze_simulated_sentiment()` MUST set `is_real_data=False`
- NEVER fabricate auditor sentiment without explicit proxy flag

---

### `auditgpt.reporting`
**Purpose**: Report generation and formatting

- `sections.py`: Generate required report sections
- `formatter.py`: Plain text and JSON output

**Required Report Sections**:
1. Executive Summary (one paragraph, dual scores)
2. Manipulation/Fraud-Risk Signals (with citations)
3. Financial-Stress/Asset-Quality Signals (separate)
4. Red-Flag Timeline (year by year)
5. Auditor Note Trend (real or "unavailable")
6. Related-Party Trend (real or "proxy only")
7. Peer Selection Explanation
8. Peer Comparison Table
9. Missing Data Disclosures

---

### `auditgpt.api`
**Purpose**: Main facade and entry point

- `engine.py`: `AuditGPT` class orchestrating all modules

**Contracts**:
- MUST return `AnalysisResult` with all components
- MUST include `AnalysisTiming` for performance tracking
- MUST handle errors gracefully with `success` flag

---

## Sector-Specific Rules

### Banks (HDFC, ICICI, AXIS, SBI, etc.)
- SKIP CFO/NP divergence analysis
- SKIP Other Income as RPT proxy
- ALWAYS include NPA stress signals
- ALWAYS separate stress from manipulation
- Use bank-specific peer groups (PSU vs Private)

### NBFCs (BAJFINANCE, MUTHOOTFIN, etc.)
- Similar to banks for stress/manipulation separation
- CAR threshold: 15% (higher than banks)

### IT Services (TCS, INFY, WIPRO, etc.)
- Lower D/E threshold (0.5 vs 2.0)
- Higher CFO quality expectations

### Realty (DLF, GODREJPROP, etc.)
- Longer receivable cycles acceptable
- Higher leverage thresholds

---

## Testing Requirements

1. **Regression Tests**: YESBANK = CRITICAL, TCS = LOW
2. **Evidence Integrity**: Every signal has at least one evidence ref
3. **No Fabrication**: Report text never claims unverified citations
4. **Bank Separation**: Bank stress signals dominate over manipulation
5. **Edge Cases**: Handle negative CFO, missing years, partial data
