#!/usr/bin/env python3
"""
AuditGPT API Server
FastAPI server that exposes the AuditGPT forensic analysis engine as a REST API.
"""

import os
import sys
from typing import Optional

# Ensure auditgpt package is importable
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

from audit_gpt_v2 import AuditGPT

# Initialize FastAPI app
app = FastAPI(
    title="AuditGPT API",
    description="Financial Statement Forensics Engine - AI-powered fraud detection and risk analysis",
    version="2.0.0",
)

# Add CORS middleware to allow frontend connections
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",  # Vite dev server
        "http://localhost:5174",  # Vite dev server (alternate port)
        "http://localhost:3000",  # Alternative React port
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
        "http://127.0.0.1:3000",
        "http://localhost:4173",  # Vite preview
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize AuditGPT engine (singleton)
engine = AuditGPT(verbose=True)


class AnalysisRequest(BaseModel):
    """Request model for analysis endpoint."""
    ticker: str
    sector: Optional[str] = None
    peers: Optional[list] = None


class HealthResponse(BaseModel):
    """Health check response model."""
    status: str
    version: str
    engine: str


@app.get("/", response_model=HealthResponse)
async def root():
    """Root endpoint - health check."""
    return {
        "status": "healthy",
        "version": "2.0.0",
        "engine": "AuditGPT Financial Statement Forensics"
    }


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "version": "2.0.0",
        "engine": "AuditGPT Financial Statement Forensics"
    }


@app.get("/api/analyze/{ticker}")
async def analyze_company(ticker: str, sector: Optional[str] = None):
    """
    Analyze a company for forensic red flags.
    
    Args:
        ticker: Company ticker symbol (e.g., HDFCBANK, TCS, YESBANK)
        sector: Optional sector override (auto-detected if not provided)
    
    Returns:
        Complete analysis result including risk scores, anomalies, peer comparison, etc.
    """
    ticker = ticker.upper().strip()
    
    if not ticker:
        raise HTTPException(status_code=400, detail="Ticker symbol is required")
    
    if len(ticker) > 20:
        raise HTTPException(status_code=400, detail="Invalid ticker symbol")
    
    try:
        print(f"\n[API] Analyzing {ticker}...")
        result = engine.analyze(ticker, sector=sector)
        
        if result is None:
            raise HTTPException(
                status_code=404,
                detail=f"Unable to analyze {ticker}. Company data may not be available."
            )
        
        print(f"[API] Analysis complete for {ticker}")
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"[API] Error analyzing {ticker}: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Analysis failed: {str(e)}"
        )


@app.post("/api/analyze")
async def analyze_company_post(request: AnalysisRequest):
    """
    Analyze a company for forensic red flags (POST method).
    
    Accepts JSON body with ticker, optional sector, and optional peers list.
    """
    return await analyze_company(request.ticker, request.sector)


@app.get("/api/tickers")
async def get_available_tickers():
    """
    Get a list of commonly available ticker symbols for analysis.
    """
    return {
        "categories": {
            "banks": ["HDFCBANK", "ICICIBANK", "SBIN", "AXISBANK", "KOTAKBANK", "YESBANK", "BANKBARODA", "PNB"],
            "nbfc": ["BAJFINANCE", "MUTHOOTFIN", "CHOLAFIN", "SBICARD", "JIOFIN", "PAYTM"],
            "it_services": ["TCS", "INFY", "WIPRO", "HCLTECH", "TECHM", "LTI"],
            "realty": ["DLF", "GODREJPROP", "OBEROIRLTY", "PRESTIGE"],
            "pharma": ["SUNPHARMA", "DRREDDY", "CIPLA", "DIVISLAB"],
            "auto": ["MARUTI", "TATAMOTORS", "M&M", "BAJAJ-AUTO"],
            "conglomerate": ["RELIANCE", "ITC", "ADANIENT"],
        },
        "note": "These are examples. The engine can analyze any company available on screener.in"
    }


if __name__ == "__main__":
    print("\n" + "=" * 70)
    print("        AUDITGPT v2.0 API SERVER")
    print("   Financial Statement Forensics Engine")
    print("=" * 70)
    print("\n🚀 Starting server on http://localhost:8000")
    print("📖 API docs available at http://localhost:8000/docs")
    print("-" * 70 + "\n")
    
    uvicorn.run(
        "server:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
