"""Named family-weight profiles for T5b Lab / research (observation-only).

Profiles are versioned configs — never applied as live decision scores.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.confluence.families import ConfluenceFamily
from app.confluence.weights import (
    DEFAULT_FAMILY_WEIGHTS,
    FAMILY_WEIGHTS_VERSION,
    FamilyWeightsConfig,
)

D = ConfluenceFamily.DIRECTION.value
P = ConfluenceFamily.PARTICIPATION.value
S = ConfluenceFamily.STRUCTURE.value
L = ConfluenceFamily.LOCATION.value
R = ConfluenceFamily.REGIME.value


@dataclass(frozen=True)
class FamilyWeightProfile:
    id: str
    label: str
    config: FamilyWeightsConfig
    description: str = ""


def _cfg(weights: dict[str, float], version: str | None = None) -> FamilyWeightsConfig:
    cfg = FamilyWeightsConfig(
        version=version or FAMILY_WEIGHTS_VERSION,
        weights=weights,
    )
    cfg.validate()
    return cfg


BALANCED = FamilyWeightProfile(
    id="balanced_v0",
    label="Balanced",
    description="Default equal-role split (T5a default).",
    config=DEFAULT_FAMILY_WEIGHTS,
)

DIRECTION_HEAVY = FamilyWeightProfile(
    id="direction_heavy_v0",
    label="Direction heavy",
    description="Emphasizes Ichimoku direction stage.",
    config=_cfg({D: 0.45, P: 0.20, S: 0.15, L: 0.10, R: 0.10}),
)

PARTICIPATION_HEAVY = FamilyWeightProfile(
    id="participation_heavy_v0",
    label="Participation heavy",
    description="Emphasizes RVOL / participation stage.",
    config=_cfg({D: 0.20, P: 0.40, S: 0.15, L: 0.15, R: 0.10}),
)

STRUCTURE_HEAVY = FamilyWeightProfile(
    id="structure_heavy_v0",
    label="Structure heavy",
    description="Emphasizes structure stage.",
    config=_cfg({D: 0.20, P: 0.15, S: 0.40, L: 0.15, R: 0.10}),
)

FAMILY_WEIGHT_PROFILES: dict[str, FamilyWeightProfile] = {
    p.id: p
    for p in (BALANCED, DIRECTION_HEAVY, PARTICIPATION_HEAVY, STRUCTURE_HEAVY)
}


def list_family_weight_profiles() -> list[FamilyWeightProfile]:
    return list(FAMILY_WEIGHT_PROFILES.values())


def get_family_weight_profile(profile_id: str) -> FamilyWeightProfile:
    try:
        return FAMILY_WEIGHT_PROFILES[profile_id]
    except KeyError as exc:
        raise KeyError(f"unknown family weight profile: {profile_id!r}") from exc
