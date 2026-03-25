"""
AuditGPT - Financial Statement Forensics Engine
"The AI That Reads 10 Years of Financial Statements and Finds What the Auditors Missed"

A hybrid deterministic + AI forensic engine for NSE-listed companies.
"""

__version__ = "2.0.0"
__author__ = "AuditGPT Team"

from auditgpt.api.engine import AuditGPT

__all__ = ["AuditGPT"]
