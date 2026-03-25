# AuditGPT v2.0

**Financial Statement Forensics Engine**

*"The AI That Reads 10 Years of Financial Statements and Finds What the Auditors Missed"*

## Overview

AuditGPT is an AI-powered forensic analysis tool that detects financial red flags, manipulation signals, and stress indicators in company financial statements. It provides dual-risk scoring, peer benchmarking, and explainable AI insights.

## Features

- **Dual Scoring Engine**: Separate manipulation risk and financial stress scores
- **Evidence-First Architecture**: Every signal backed by citations from financial data
- **Bank-Specific Analysis**: Specialized signals for NPA, CAR, provisioning
- **Dynamic Peer Benchmarking**: Compare against sector peers using robust statistics
- **Explainable AI**: Transparent signal contributions and evidence chains
- **Real-Time Dashboard**: Interactive React frontend with visualizations

## Tech Stack

### Backend
- Python 3.x
- FastAPI (REST API)
- Modular architecture (signals, scoring, evidence, reporting)

### Frontend
- React 19 + TypeScript
- Tailwind CSS
- Recharts (data visualization)
- Vite (build tool)

## Project Structure

```
├── audit_gpt_v2.py          # Main entry point (backward-compatible wrapper)
├── auditgpt/                # Core analysis engine
│   ├── ai/                  # NLP, retrieval, sentiment analysis
│   ├── api/                 # Main facade and orchestration
│   ├── benchmarking/        # Peer selection and statistics
│   ├── config/              # Constants and thresholds
│   ├── evidence/            # Evidence tracking and citations
│   ├── extraction/          # PDF parsing and note extraction
│   ├── ingestion/           # Data acquisition (screener, CSV, cache)
│   ├── reporting/           # Report generation
│   ├── scoring/             # Dual scoring with Forensic Sigmoid
│   ├── signals/             # Signal detection (manipulation, stress, bank-specific)
│   └── tests/               # Unit tests
└── frontend/                # React dashboard
    ├── src/
    │   ├── components/      # Reusable UI components
    │   └── pages/           # Dashboard and Home pages
    └── package.json
```

## Quick Start

### Backend

```bash
# Install dependencies
pip install -r requirements.txt

# Run the API server
python server.py
# Server runs on http://localhost:8000
```

### Frontend

```bash
cd frontend

# Install dependencies
npm install

# Run development server
npm run dev
# Frontend runs on http://localhost:5173
```

## Usage

1. Start the backend server
2. Start the frontend development server
3. Open `http://localhost:5173` in your browser
4. Enter a company ticker (e.g., `YESBANK`, `SBIN`, `TCS`)
5. View the comprehensive forensic analysis

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/analyze/{ticker}` | GET | Analyze a company |
| `/api/tickers` | GET | Get available ticker symbols |
| `/health` | GET | Health check |

## Supported Companies

The engine can analyze any company available on screener.in, including:
- **Banks**: HDFCBANK, ICICIBANK, SBIN, AXISBANK, KOTAKBANK, YESBANK
- **NBFC**: BAJFINANCE, MUTHOOTFIN, JIOFIN, PAYTM
- **IT Services**: TCS, INFY, WIPRO, HCLTECH
- **Others**: DLF, RELIANCE, ITC, and more

## Risk Scoring

- **Manipulation Score**: Fraud-risk indicators (CFO divergence, quality issues)
- **Stress Score**: Financial stress indicators (leverage, liquidity, asset quality)
- **Combined Score**: Weighted combination (60% manipulation + 40% stress)

Score Range: 8 to 95 (no company is perfect, no company is hopeless)

## License

MIT License

## Author

Parth Talsania
