# AuditGPT Development Rules

## Non-Negotiable Rules

### Evidence-First Architecture
Every signal MUST reference its source:
- Financial statement signals → line item + year
- Note-based signals → page number + paragraph index
- Ratio signals → formula + source values

**Bad**:
```python
signal = Signal(explanation="Revenue quality declining")
```

**Good**:
```python
signal = Signal(
    explanation="Revenue quality declining",
    evidence_refs=[
        EvidenceRef(ref_type=RefType.STATEMENT, filing_year=2024, 
                   statement_type="P&L", line_item="Revenue")
    ]
)
```

### No Data Fabrication
When data is unavailable, explicitly state it:

**Bad**:
```python
# Generating mock sentiment because PDF not available
sentiment = {"score": 0.7, "trend": "stable"}
```

**Good**:
```python
if not pdf_available:
    return {
        "available": False,
        "is_real_data": False,
        "reason": "No annual report PDF provided"
    }
```

### Bank Sector Separation
For BANK/NBFC sectors, ALWAYS separate stress from manipulation:

**Bad**:
```python
# Single fraud score for all sectors
score = calculate_fraud_score(signals)
```

**Good**:
```python
if sector in BANK_SECTORS:
    manipulation_score = score_manipulation_signals(signals)
    stress_score = score_stress_signals(signals)
    return DualScore(manipulation=manipulation_score, stress=stress_score)
```

### CFO Analysis Safety
Never compute CFO growth with non-positive baseline:

**Bad**:
```python
cfo_growth = (cfo_current - cfo_base) / cfo_base * 100  # Crashes if cfo_base <= 0
```

**Good**:
```python
if cfo_base is None or cfo_base <= 0:
    continue  # Skip comparison
cfo_growth = (cfo_current - cfo_base) / cfo_base * 100
```

### RPT Proxy Restrictions
"Other Income" as RPT proxy is DISABLED for financial sectors:

```python
if sector in ('BANK', 'FINANCE', 'NBFC'):
    return []  # Skip Other Income proxy
```

### Scoring Constraints
- Base risk: 8-10 (no company is perfect)
- Max score: 95 (avoid certainty claims)
- Use Forensic Sigmoid transformation
- Combined = 0.6 * manipulation + 0.4 * stress

### Peer Selection Requirements
- Filter by sector (exact match)
- Filter by size (0.3x to 3x revenue)
- Use robust statistics (median, IQR)
- Explain selection reasoning

---

## Code Style

### Signal Creation
Always use the factory function:
```python
signal = create_signal(
    signal_id="REV_CFO_DIV_2024",
    family=SignalFamily.REVENUE_DIVERGENCE,
    category=SignalCategory.MANIPULATION,
    severity=SignalSeverity.HIGH,
    year_first=2023,
    year_latest=2024,
    evidence_refs=[...],
    explanation="Revenue grew 25% while CFO declined 15%"
)
```

### Threshold Lookups
Always use sector-aware thresholds:
```python
threshold = SectorThresholds().get_threshold(
    metric='debt_equity',
    sector='IT'
)  # Returns 0.5 instead of default 2.0
```

### Error Handling
Return structured errors, don't crash:
```python
try:
    result = analyze(company)
except Exception as e:
    return AnalysisResult(
        success=False,
        error_message=str(e)
    )
```

---

## Performance Guidelines

- Target: Complete analysis in < 90 seconds
- Cache all scraped data with TTL
- Lazy-load PDF parsing
- Use batch operations where possible
- Profile with AnalysisTiming

---

## Testing Requirements

### Regression Suite
```python
# These assertions must always pass
assert analyze("YESBANK").dual_score.combined_level == "CRITICAL"
assert analyze("TCS").dual_score.combined_level == "LOW"
```

### Evidence Integrity
```python
for signal in result.signals:
    assert len(signal.evidence_refs) >= 1
    for ref in signal.evidence_refs:
        assert ref.citation_string  # Non-empty
```

### No Fabrication Test
```python
# Report should not claim unavailable data
if not pdf_provided:
    assert "unavailable" in result.sentiment_section.lower()
    assert "real" not in result.sentiment_section.lower()
```
