"""IchiVol Evidence Engine — SIGNAL → PREUVES → DÉCISION → RÉSULTAT → MESURE.

This package does NOT invent BUY/SELL. It packages reproducible evidence
around a SignalContext (historical matches, forward outcomes, ablation
deltas, sample-size quality) so the Decision Engine and UI can explain
accept / refuse / invalidate from observations, not invented confidence.
"""

from __future__ import annotations

from app.evidence.context import FEATURE_VERSION, SignalContext, build_signal_context
from app.evidence.engine import EvidenceEngine, EvidenceReport, evaluate_evidence
from app.evidence.sample import SampleQuality, classify_sample
from app.evidence.versions import EVIDENCE_ENGINE_VERSION, RULES_VERSION

__all__ = [
    "FEATURE_VERSION",
    "EVIDENCE_ENGINE_VERSION",
    "RULES_VERSION",
    "SignalContext",
    "build_signal_context",
    "EvidenceEngine",
    "EvidenceReport",
    "evaluate_evidence",
    "SampleQuality",
    "classify_sample",
]
