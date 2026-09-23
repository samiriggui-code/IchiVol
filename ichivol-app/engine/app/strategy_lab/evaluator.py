"""Evaluate a Ruleset against a causal FeatureSeries.

Rising-edge only: a signal fires when all conditions become true on bar i
after being false (or incomplete) on bar i-1. This avoids counting the same
setup on every bar of a multi-bar regime as separate hypotheses.
"""

from __future__ import annotations

from app.agents.types import Direction
from app.strategy_lab.conditions import CONDITION_REGISTRY
from app.strategy_lab.features import FeatureBar, FeatureSeries
from app.strategy_lab.ruleset import ConditionGroup, ConditionValue, Ruleset


def _condition_holds(
    bar: FeatureBar,
    key: str,
    expected: ConditionValue,
    direction: Direction,
) -> bool:
    spec = CONDITION_REGISTRY.get(key)
    if spec is None:
        return False
    return spec.holds(bar, expected, direction)


def bar_matches_group(
    bar: FeatureBar,
    group: ConditionGroup,
    direction: Direction,
) -> bool:
    """AND of ``all_of`` leaves (if any) and OR of ``any_of`` leaves (if any)."""
    if group.all_of:
        if not all(
            _condition_holds(bar, key, value, direction)
            for key, value in group.all_of.items()
        ):
            return False
    if group.any_of:
        if not any(
            _condition_holds(bar, key, value, direction)
            for key, value in group.any_of.items()
        ):
            return False
    return bool(group.all_of or group.any_of)


def bar_matches(bar: FeatureBar, ruleset: Ruleset) -> bool:
    return bar_matches_group(bar, ruleset.condition_group, ruleset.direction)


def extract_ruleset_signals(
    features: FeatureSeries,
    ruleset: Ruleset,
    *,
    rising_edge: bool = True,
) -> list[tuple[int, Direction]]:
    """Return (signal_index, direction) pairs for Event Study."""
    matches = [bar_matches(bar, ruleset) for bar in features.bars]
    out: list[tuple[int, Direction]] = []
    for i, ok in enumerate(matches):
        if not ok:
            continue
        if rising_edge and i > 0 and matches[i - 1]:
            continue
        out.append((i, ruleset.direction))
    return out


def matches_mask(features: FeatureSeries, ruleset: Ruleset) -> list[bool]:
    return [bar_matches(bar, ruleset) for bar in features.bars]
