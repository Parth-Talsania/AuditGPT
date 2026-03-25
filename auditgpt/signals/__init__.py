"""Signals module for AuditGPT - anomaly detection and classification."""

from auditgpt.signals.base import (
    Signal,
    SignalSeverity,
    SignalCategory,
    SignalFamily,
    create_signal,
)
from auditgpt.signals.manipulation import ManipulationSignalDetector
from auditgpt.signals.stress import StressSignalDetector
from auditgpt.signals.bank_specific import BankSignalDetector

# Aliases for shorter names
ManipulationDetector = ManipulationSignalDetector
StressDetector = StressSignalDetector

__all__ = [
    "Signal",
    "SignalSeverity",
    "SignalCategory",
    "SignalFamily",
    "create_signal",
    "ManipulationSignalDetector",
    "StressSignalDetector",
    "BankSignalDetector",
    "ManipulationDetector",
    "StressDetector",
]
