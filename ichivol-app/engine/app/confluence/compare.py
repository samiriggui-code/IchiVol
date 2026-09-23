"""Compare named weight profiles on one PipelineResult (T5b)."""

from __future__ import annotations

from app.confluence.observe import observe_family_weights
from app.confluence.profiles import FAMILY_WEIGHT_PROFILES, FamilyWeightProfile
from app.decision.pipeline import PipelineResult


def compare_family_weight_profiles(
    pipeline: PipelineResult,
    profiles: dict[str, FamilyWeightProfile] | None = None,
) -> dict:
    """Observation table: weighted_support per profile. Does not alter pipeline."""
    catalog = profiles or FAMILY_WEIGHT_PROFILES
    rows: dict[str, dict] = {}
    for pid, profile in catalog.items():
        obs = observe_family_weights(pipeline, profile.config)
        rows[pid] = {
            "id": pid,
            "label": profile.label,
            "description": profile.description,
            "version": obs.version,
            "weights": obs.weights,
            "family_status": obs.family_status,
            "family_contribution": obs.family_contribution,
            "weighted_support": obs.weighted_support,
        }
    return {
        "pipeline_decision": pipeline.decision,
        "pipeline_strategy_version": pipeline.strategy_version,
        "disclaimer": (
            "Family weight profile comparison — observation only; "
            "does not alter decision or confidence."
        ),
        "profiles": rows,
    }
