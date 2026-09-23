"""Evaluate a Ruleset against a causal FeatureSeries.

Rising-edge only: a signal fires when all conditions become true on bar i
after being false (or incomplete) on bar i-1. This avoids counting the same
setup on every bar of a multi-bar regime as separate hypotheses.
"""

from __future__ import annotations

from app.agents.types import Direction
from app.strategy_lab.features import FeatureBar, FeatureSeries
from app.strategy_lab.ruleset import ConditionValue, Ruleset


def _condition_holds(
    bar: FeatureBar,
    key: str,
    expected: ConditionValue,
    direction: Direction,
) -> bool:
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
    # --- Ichimoku Analytics ---
    if key == "kijun_slope":
        return bar.kijun_slope_state == str(expected)
    if key == "price_kijun_distance_atr_min":
        return (
            bar.price_kijun_distance_atr is not None
            and bar.price_kijun_distance_atr >= float(expected)
        )
    if key == "price_kijun_distance_atr_max":
        return (
            bar.price_kijun_distance_atr is not None
            and bar.price_kijun_distance_atr <= float(expected)
        )
    if key == "kijun_break_bullish":
        return bar.kijun_break_bullish == expected
    if key == "kijun_break_bearish":
        return bar.kijun_break_bearish == expected
    if key == "kijun_retest":
        hit = (
            bar.kijun_retest_bullish
            if direction == Direction.LONG
            else bar.kijun_retest_bearish
        )
        return hit == bool(expected)
    if key == "kijun_bounce":
        hit = (
            bar.kijun_bounce_bullish
            if direction == Direction.LONG
            else bar.kijun_bounce_bearish
        )
        return hit == bool(expected)
    if key == "kumo_orientation":
        return bar.kumo_orientation == str(expected)
    if key == "kumo_twist_age_max":
        return (
            bar.bars_since_kumo_twist is not None
            and bar.bars_since_kumo_twist <= int(expected)
        )
    if key == "kumo_thickness_atr_min":
        return (
            bar.kumo_thickness_atr is not None
            and bar.kumo_thickness_atr >= float(expected)
        )
    if key == "kumo_thickness_atr_max":
        return (
            bar.kumo_thickness_atr is not None
            and bar.kumo_thickness_atr <= float(expected)
        )
    # --- T-EXP experimental (PPO / BEST Cloud) ---
    if key == "ppo_above_signal":
        return bar.ppo_above_signal == expected
    if key == "ppo_below_signal":
        return bar.ppo_below_signal == expected
    if key == "ppo_above_zero":
        return bar.ppo_above_zero == expected
    if key == "ppo_below_zero":
        return bar.ppo_below_zero == expected
    if key == "ppo_histogram_rising":
        return bar.ppo_histogram_rising == expected
    if key == "ppo_histogram_falling":
        return bar.ppo_histogram_falling == expected
    if key == "ppo_signal_cross_bullish":
        return bar.ppo_signal_cross_bullish == expected
    if key == "ppo_signal_cross_bearish":
        return bar.ppo_signal_cross_bearish == expected
    if key == "ppo_cross_age_max":
        age = (
            bar.ppo_cross_age_bullish
            if direction == Direction.LONG
            else bar.ppo_cross_age_bearish
        )
        return age is not None and age <= int(expected)
    if key == "ppo_min":
        return bar.ppo is not None and bar.ppo >= float(expected)
    if key == "ppo_max":
        return bar.ppo is not None and bar.ppo <= float(expected)
    if key == "ppo_momentum":
        return bar.ppo_momentum == str(expected)
    if key == "best_cloud_trend":
        return bar.best_cloud_trend == str(expected)
    if key == "best_cloud_bullish":
        return bar.best_cloud_bullish == expected
    if key == "best_cloud_bearish":
        return bar.best_cloud_bearish == expected
    if key == "best_cloud_inside":
        return bar.best_cloud_inside == expected
    if key == "best_cloud_cross_bullish":
        return bar.best_cloud_cross_bullish == expected
    if key == "best_cloud_cross_bearish":
        return bar.best_cloud_cross_bearish == expected
    if key == "best_cloud_cross_age_max":
        age = (
            bar.best_cloud_cross_age_bullish
            if direction == Direction.LONG
            else bar.best_cloud_cross_age_bearish
        )
        return age is not None and age <= int(expected)
    return False


def bar_matches(bar: FeatureBar, ruleset: Ruleset) -> bool:
    """AND of ``all_of`` leaves (if any) and OR of ``any_of`` leaves (if any)."""
    group = ruleset.condition_group
    if group.all_of:
        if not all(
            _condition_holds(bar, key, value, ruleset.direction)
            for key, value in group.all_of.items()
        ):
            return False
    if group.any_of:
        if not any(
            _condition_holds(bar, key, value, ruleset.direction)
            for key, value in group.any_of.items()
        ):
            return False
    return bool(group.all_of or group.any_of)


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
