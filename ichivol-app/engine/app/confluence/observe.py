"""Observe weighted family support from a PipelineResult (T5a).

Does not mutate pipeline stages, decision labels, or combiner confidence.
``weighted_support`` is a research/display scalar — not a live score.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.confluence.families import ALL_FAMILIES
from app.confluence.weights import DEFAULT_FAMILY_WEIGHTS, FamilyWeightsConfig
from app.decision.pipeline import PipelineResult

_DISCLAIMER = (
    "Family weights observation — does not alter decision or confidence."
)


@dataclass(frozen=True)
class FamilyWeightsObservation:
    version: str
    weights: dict[str, float]
    family_status: dict[str, str]
    family_contribution: dict[str, float]
    weighted_support: float
    pipeline_decision: str
    pipeline_strategy_version: str
    disclaimer: str = _DISCLAIMER

    def to_dict(self) -> dict:
        return {
            "version": self.version,
            "weights": dict(self.weights),
            "family_status": dict(self.family_status),
            "family_contribution": dict(self.family_contribution),
            "weighted_support": self.weighted_support,
            "pipeline_decision": self.pipeline_decision,
            "pipeline_strategy_version": self.pipeline_strategy_version,
            "disclaimer": self.disclaimer,
        }


def observe_family_weights(
    pipeline: PipelineResult,
    config: FamilyWeightsConfig = DEFAULT_FAMILY_WEIGHTS,
) -> FamilyWeightsObservation:
    """Map pipeline stage statuses → weighted_support (observation only)."""
    config.validate()
    by_id = {s.id.value: s for s in pipeline.stages}
    family_status: dict[str, str] = {}
    family_contribution: dict[str, float] = {}
    total = 0.0
    for fam in ALL_FAMILIES:
        key = fam.value
        stage = by_id.get(key)
        status = stage.status.value if stage is not None else "pending"
        family_status[key] = status
        score = float(config.status_scores.get(status, 0.0))
        w = float(config.weights[key])
        contrib = round(w * score, 6)
        family_contribution[key] = contrib
        total += contrib
    return FamilyWeightsObservation(
        version=config.version,
        weights={k: float(v) for k, v in config.weights.items()},
        family_status=family_status,
        family_contribution=family_contribution,
        weighted_support=round(total, 6),
        pipeline_decision=pipeline.decision,
        pipeline_strategy_version=pipeline.strategy_version,
    )


def family_weights_observation_dict(
    obs: FamilyWeightsObservation | None,
) -> dict | None:
    if obs is None:
        return None
    return obs.to_dict()
