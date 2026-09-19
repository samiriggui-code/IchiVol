"""Version stamps for evidence / rules / features.

Every persisted decision and EvidenceReport carries these so results from
two engine versions are never compared blindly.
"""

from __future__ import annotations

EVIDENCE_ENGINE_VERSION = "evidence_v1"
RULES_VERSION = "pipeline_gates_v1"
