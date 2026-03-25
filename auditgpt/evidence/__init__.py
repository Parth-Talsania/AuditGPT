"""Evidence module for AuditGPT - handles citations and source references."""

from auditgpt.evidence.models import (
    EvidenceRef,
    NoteChunk,
    StatementRef,
    SentimentTrend,
    SentimentYear,
)
from auditgpt.evidence.store import EvidenceStore

__all__ = [
    "EvidenceRef",
    "NoteChunk", 
    "StatementRef",
    "SentimentTrend",
    "SentimentYear",
    "EvidenceStore",
]
