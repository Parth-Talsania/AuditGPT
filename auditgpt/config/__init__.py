"""Configuration module for AuditGPT."""

from auditgpt.config.constants import (
    FRAUD_PATTERNS,
    INDUSTRY_NORMS,
    SECTOR_MAPPING,
    PEER_UNIVERSES,
)
from auditgpt.config.thresholds import SectorThresholds

__all__ = [
    "FRAUD_PATTERNS",
    "INDUSTRY_NORMS", 
    "SECTOR_MAPPING",
    "PEER_UNIVERSES",
    "SectorThresholds",
]
