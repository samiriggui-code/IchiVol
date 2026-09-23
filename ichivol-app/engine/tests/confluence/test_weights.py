"""T5a — FamilyWeightsConfig invariants."""

from __future__ import annotations

import pytest

from app.confluence.families import ALL_FAMILIES, ConfluenceFamily
from app.confluence.weights import (
    DEFAULT_FAMILY_WEIGHTS,
    FAMILY_WEIGHTS_VERSION,
    FamilyWeightsConfig,
)


def test_default_weights_sum_to_one():
    DEFAULT_FAMILY_WEIGHTS.validate()
    assert abs(sum(DEFAULT_FAMILY_WEIGHTS.weights.values()) - 1.0) < 1e-12


def test_default_keys_match_all_families():
    assert set(DEFAULT_FAMILY_WEIGHTS.weights) == {f.value for f in ALL_FAMILIES}


def test_default_version():
    assert DEFAULT_FAMILY_WEIGHTS.version == FAMILY_WEIGHTS_VERSION
    assert FAMILY_WEIGHTS_VERSION.startswith("family_weights_")


def test_reject_missing_key():
    cfg = FamilyWeightsConfig(
        weights={
            ConfluenceFamily.DIRECTION.value: 0.4,
            ConfluenceFamily.PARTICIPATION.value: 0.3,
            ConfluenceFamily.STRUCTURE.value: 0.3,
            # location + regime missing
        }
    )
    with pytest.raises(ValueError, match="missing"):
        cfg.validate()


def test_reject_extra_key():
    w = dict(DEFAULT_FAMILY_WEIGHTS.weights)
    w["momentum"] = 0.0
    cfg = FamilyWeightsConfig(weights=w)
    with pytest.raises(ValueError, match="extra"):
        cfg.validate()


def test_reject_sum_not_one():
    w = {f.value: 0.3 for f in ALL_FAMILIES}  # sum = 1.5
    cfg = FamilyWeightsConfig(weights=w)
    with pytest.raises(ValueError, match="sum to 1"):
        cfg.validate()


def test_reject_negative_weight():
    w = dict(DEFAULT_FAMILY_WEIGHTS.weights)
    w[ConfluenceFamily.DIRECTION.value] = -0.1
    w[ConfluenceFamily.PARTICIPATION.value] = 0.65
    cfg = FamilyWeightsConfig(weights=w)
    with pytest.raises(ValueError, match="non-negative"):
        cfg.validate()
