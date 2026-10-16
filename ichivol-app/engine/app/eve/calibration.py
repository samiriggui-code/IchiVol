"""V1-G — policy calibration (thresholds / weights), NOT LLM weight training."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from typing import Any

from app.eve.coherence import COHERENCE_POLICY_V1

DEFAULT_POLICY: dict[str, Any] = {
    "version": "eve.policy.v1",
    "created_at": "2026-10-16T00:00:00+00:00",
    "kind": "calibration_policy",
    "not": "llm_finetune",
    "routing": {
        "use_jev_analyst": True,
        "use_jev_challenger": True,
        "use_jev_guardian": True,
        "use_jev_shadow": True,
        "skip_jev_if_data_quality_below": 0.15,
    },
    "thresholds": {
        "min_data_quality_to_act": 0.35,
        "max_contradictions_before_abstain": 4,
        "guardian_critical_forces_abstain": True,
    },
    "coherence": deepcopy(COHERENCE_POLICY_V1),
}


def active_policy(override: dict[str, Any] | None = None) -> dict[str, Any]:
    pol = deepcopy(DEFAULT_POLICY)
    if override:
        for key, value in override.items():
            if key in ("routing", "thresholds", "coherence") and isinstance(value, dict):
                pol[key] = {**pol.get(key, {}), **value}
            else:
                pol[key] = value
    pol["loaded_at"] = datetime.now(timezone.utc).isoformat()
    return pol


def propose_adjustment(
    *,
    policy: dict[str, Any],
    observed: dict[str, Any],
) -> dict[str, Any]:
    """Document a proposed calibration change from historical observations.

    Does not mutate live policy automatically — versioned suggestion only.
    """
    suggestion = {
        "schema": "ichivol.eve.calibration_proposal.v1",
        "base_version": policy.get("version"),
        "proposed_at": datetime.now(timezone.utc).isoformat(),
        "observed": observed,
        "changes": [],
        "status": "proposal",
        "applied": False,
        "not": "llm_retraining",
    }
    abstain_rate = observed.get("abstain_rate")
    if isinstance(abstain_rate, (int, float)) and abstain_rate > 0.8:
        suggestion["changes"].append(
            {
                "path": "thresholds.min_data_quality_to_act",
                "from": policy.get("thresholds", {}).get("min_data_quality_to_act"),
                "to": 0.30,
                "reason": "high_abstain_rate",
            }
        )
    mean_coherence = observed.get("mean_coherence")
    if isinstance(mean_coherence, (int, float)) and mean_coherence < 0.4:
        suggestion["changes"].append(
            {
                "path": "coherence.weights.data_quality",
                "reason": "low_mean_coherence_review_weights",
                "note": "Manual review required before applying",
            }
        )
    return suggestion
