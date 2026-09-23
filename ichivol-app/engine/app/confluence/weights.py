"""Versioned family-weight config for confluence observation (T5a).

Defaults are placeholders for Lab / research display. They MUST NOT feed
live decision labels or confidence until a later T5 slice backs them with
ablation / walk-forward evidence.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.confluence.families import ALL_FAMILIES, ConfluenceFamily

FAMILY_WEIGHTS_VERSION = "family_weights_v0"

_DEFAULT_WEIGHTS: dict[str, float] = {
    ConfluenceFamily.DIRECTION.value: 0.30,
    ConfluenceFamily.PARTICIPATION.value: 0.25,
    ConfluenceFamily.STRUCTURE.value: 0.20,
    ConfluenceFamily.LOCATION.value: 0.15,
    ConfluenceFamily.REGIME.value: 0.10,
}

_DEFAULT_STATUS_SCORES: dict[str, float] = {
    "pass": 1.0,
    "watch": 0.0,
    "fail": -1.0,
    "pending": 0.0,
    "skip": 0.0,
}


@dataclass(frozen=True)
class FamilyWeightsConfig:
    """Frozen weight vector + status→score map. Observation only.

    ``weights`` keys must be exactly the five pipeline family ids.
    """

    version: str = FAMILY_WEIGHTS_VERSION
    weights: dict[str, float] = field(
        default_factory=lambda: dict(_DEFAULT_WEIGHTS)
    )
    status_scores: dict[str, float] = field(
        default_factory=lambda: dict(_DEFAULT_STATUS_SCORES)
    )

    def validate(self) -> None:
        expected = {f.value for f in ALL_FAMILIES}
        keys = set(self.weights)
        if keys != expected:
            missing = expected - keys
            extra = keys - expected
            raise ValueError(
                f"family weights keys mismatch: missing={sorted(missing)} "
                f"extra={sorted(extra)}"
            )
        for k, v in self.weights.items():
            if not isinstance(v, (int, float)) or v < 0:
                raise ValueError(f"weight for {k!r} must be non-negative number, got {v!r}")
        total = sum(float(v) for v in self.weights.values())
        if abs(total - 1.0) > 1e-9:
            raise ValueError(f"family weights must sum to 1.0 (±1e-9), got {total}")


DEFAULT_FAMILY_WEIGHTS = FamilyWeightsConfig()
DEFAULT_FAMILY_WEIGHTS.validate()
