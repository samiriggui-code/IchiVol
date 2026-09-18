"""Evaluate a Ruleset against a causal FeatureSeries.

Rising-edge only: a signal fires when all conditions become true on bar i
after being false (or incomplete) on bar i-1. This avoids counting the same
setup on every bar of a multi-bar regime as separate hypotheses.
"""

from __future__ import annotations

from app.agents.types import Direction
from app.strategy_lab.features import FeatureBar, FeatureSeries
from app.strategy_lab.ruleset import Ruleset


def _condition_holds(bar: FeatureBar, key: str, expected: bool | int | float, direction: Direction) -> bool:
    if key == "price_above_kumo":
        return bar.price_above_kumo == expected
    if key == "price_below_kumo":
        return bar.price_below_kumo == expected
    if key == "tenkan_above_kijun":
        return bar.tenkan_above_kijun == expected
    if key == "tenkan_below_kijun":
        return bar.tenkan_below_kijun == expected
    if key == "tk_cross_bullish":
        return bar.tk_cross_bullish == expected
    if key == "tk_cross_bearish":
        return bar.tk_cross_bearish == expected
    if key == "tk_cross_age_max":
        age = (
            bar.tk_cross_age_bullish
            if direction == Direction.LONG
            else bar.tk_cross_age_bearish
        )
        return age is not None and age <= int(expected)
    if key == "kumo_breakout_bullish":
        return bar.kumo_breakout_bullish == expected
    if key == "kumo_breakout_bearish":
        return bar.kumo_breakout_bearish == expected
    if key == "rvol_min":
        return bar.rvol is not None and bar.rvol >= float(expected)
    if key == "rvol_max":
        return bar.rvol is not None and bar.rvol <= float(expected)
    if key == "bos_bullish":
        return bar.bos_bullish == expected
    if key == "bos_bearish":
        return bar.bos_bearish == expected
    if key == "structure_bias_bullish":
        return bar.structure_bias_bullish == expected
    if key == "structure_bias_bearish":
        return bar.structure_bias_bearish == expected
    if key == "atr_percentile_min":
        return bar.atr_percentile is not None and bar.atr_percentile >= float(expected)
    if key == "atr_percentile_max":
        return bar.atr_percentile is not None and bar.atr_percentile <= float(expected)
    if key == "atr_expansion":
        return bar.atr_expansion == expected
    if key == "cmf_min":
        return bar.cmf is not None and bar.cmf >= float(expected)
    if key == "cmf_max":
        return bar.cmf is not None and bar.cmf <= float(expected)
    if key == "rsi_min":
        return bar.rsi is not None and bar.rsi >= float(expected)
    if key == "rsi_max":
        return bar.rsi is not None and bar.rsi <= float(expected)
    return False


def bar_matches(bar: FeatureBar, ruleset: Ruleset) -> bool:
    return all(
        _condition_holds(bar, key, value, ruleset.direction)
        for key, value in ruleset.conditions.items()
    )


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
