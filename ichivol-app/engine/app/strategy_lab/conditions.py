"""Condition registry for Strategy Lab DSL (T3c).

One ``ConditionSpec`` declaration = one usable DSL leaf. ``CONDITION_SCHEMA``
and evaluator dispatch are derived from ``CONDITION_REGISTRY``.

``indicator_id`` must be a key in ``app.indicators.registry.REGISTRY``, or one
of the documented composites:

- ``"structure"`` — market structure / BOS fields (also a REGISTRY id)
- ``"derived"`` — direction-sensitive composites (age / retest / bounce that
  pick bullish vs bearish bar fields from trade direction)
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Mapping

from app.agents.types import Direction
from app.strategy_lab.features import FeatureBar

ConditionValue = bool | int | float | str
HoldsFn = Callable[[FeatureBar, ConditionValue, Direction], bool]


@dataclass(frozen=True)
class ConditionSpec:
    key: str
    value_type: type  # bool | int | float | str
    indicator_id: str
    holds: HoldsFn
    description: str
    allowed_values: tuple[str, ...] | None = None


def _build_registry() -> dict[str, ConditionSpec]:
    specs: list[ConditionSpec] = []

    # --- ichimoku ---
    specs.extend(
        [
            ConditionSpec(
                "price_above_kumo",
                bool,
                "ichimoku",
                lambda bar, expected, _d: bar.price_above_kumo == expected,
                "Close above the Ichimoku cloud.",
            ),
            ConditionSpec(
                "price_below_kumo",
                bool,
                "ichimoku",
                lambda bar, expected, _d: bar.price_below_kumo == expected,
                "Close below the Ichimoku cloud.",
            ),
            ConditionSpec(
                "tenkan_above_kijun",
                bool,
                "ichimoku",
                lambda bar, expected, _d: bar.tenkan_above_kijun == expected,
                "Tenkan above Kijun.",
            ),
            ConditionSpec(
                "tenkan_below_kijun",
                bool,
                "ichimoku",
                lambda bar, expected, _d: bar.tenkan_below_kijun == expected,
                "Tenkan below Kijun.",
            ),
            ConditionSpec(
                "tk_cross_bullish",
                bool,
                "ichimoku",
                lambda bar, expected, _d: bar.tk_cross_bullish == expected,
                "Bullish Tenkan/Kijun cross on this bar.",
            ),
            ConditionSpec(
                "tk_cross_bearish",
                bool,
                "ichimoku",
                lambda bar, expected, _d: bar.tk_cross_bearish == expected,
                "Bearish Tenkan/Kijun cross on this bar.",
            ),
            ConditionSpec(
                "kumo_breakout_bullish",
                bool,
                "ichimoku",
                lambda bar, expected, _d: bar.kumo_breakout_bullish == expected,
                "Bullish kumo breakout on this bar.",
            ),
            ConditionSpec(
                "kumo_breakout_bearish",
                bool,
                "ichimoku",
                lambda bar, expected, _d: bar.kumo_breakout_bearish == expected,
                "Bearish kumo breakout on this bar.",
            ),
        ]
    )

    # --- derived (direction-sensitive ichimoku age) ---
    def _tk_cross_age_max(bar: FeatureBar, expected: ConditionValue, direction: Direction) -> bool:
        age = (
            bar.tk_cross_age_bullish
            if direction == Direction.LONG
            else bar.tk_cross_age_bearish
        )
        return age is not None and age <= int(expected)

    specs.append(
        ConditionSpec(
            "tk_cross_age_max",
            int,
            "derived",
            _tk_cross_age_max,
            "Bars since last TK cross in trade direction <= N.",
        )
    )

    # --- rvol ---
    specs.extend(
        [
            ConditionSpec(
                "rvol_min",
                float,
                "rvol",
                lambda bar, expected, _d: bar.rvol is not None and bar.rvol >= float(expected),
                "Relative volume >= threshold.",
            ),
            ConditionSpec(
                "rvol_max",
                float,
                "rvol",
                lambda bar, expected, _d: bar.rvol is not None and bar.rvol <= float(expected),
                "Relative volume <= threshold.",
            ),
        ]
    )

    # --- structure ---
    specs.extend(
        [
            ConditionSpec(
                "bos_bullish",
                bool,
                "structure",
                lambda bar, expected, _d: bar.bos_bullish == expected,
                "Bullish break of structure on this bar.",
            ),
            ConditionSpec(
                "bos_bearish",
                bool,
                "structure",
                lambda bar, expected, _d: bar.bos_bearish == expected,
                "Bearish break of structure on this bar.",
            ),
            ConditionSpec(
                "structure_bias_bullish",
                bool,
                "structure",
                lambda bar, expected, _d: bar.structure_bias_bullish == expected,
                "Structure bias bullish.",
            ),
            ConditionSpec(
                "structure_bias_bearish",
                bool,
                "structure",
                lambda bar, expected, _d: bar.structure_bias_bearish == expected,
                "Structure bias bearish.",
            ),
        ]
    )

    # --- atr ---
    specs.extend(
        [
            ConditionSpec(
                "atr_percentile_min",
                float,
                "atr",
                lambda bar, expected, _d: (
                    bar.atr_percentile is not None
                    and bar.atr_percentile >= float(expected)
                ),
                "ATR percentile >= threshold.",
            ),
            ConditionSpec(
                "atr_percentile_max",
                float,
                "atr",
                lambda bar, expected, _d: (
                    bar.atr_percentile is not None
                    and bar.atr_percentile <= float(expected)
                ),
                "ATR percentile <= threshold.",
            ),
            ConditionSpec(
                "atr_expansion",
                bool,
                "atr",
                lambda bar, expected, _d: bar.atr_expansion == expected,
                "ATR expanding vs previous bar.",
            ),
        ]
    )

    # --- cmf ---
    specs.extend(
        [
            ConditionSpec(
                "cmf_min",
                float,
                "cmf",
                lambda bar, expected, _d: bar.cmf is not None and bar.cmf >= float(expected),
                "Chaikin Money Flow >= threshold.",
            ),
            ConditionSpec(
                "cmf_max",
                float,
                "cmf",
                lambda bar, expected, _d: bar.cmf is not None and bar.cmf <= float(expected),
                "Chaikin Money Flow <= threshold.",
            ),
        ]
    )

    # --- rsi ---
    specs.extend(
        [
            ConditionSpec(
                "rsi_min",
                float,
                "rsi",
                lambda bar, expected, _d: bar.rsi is not None and bar.rsi >= float(expected),
                "RSI >= threshold.",
            ),
            ConditionSpec(
                "rsi_max",
                float,
                "rsi",
                lambda bar, expected, _d: bar.rsi is not None and bar.rsi <= float(expected),
                "RSI <= threshold.",
            ),
        ]
    )

    # --- ichimoku_analytics ---
    specs.extend(
        [
            ConditionSpec(
                "kijun_slope",
                str,
                "ichimoku_analytics",
                lambda bar, expected, _d: bar.kijun_slope_state == str(expected),
                "Kijun slope state.",
                allowed_values=("RISING", "FLAT", "FALLING"),
            ),
            ConditionSpec(
                "price_kijun_distance_atr_min",
                float,
                "ichimoku_analytics",
                lambda bar, expected, _d: (
                    bar.price_kijun_distance_atr is not None
                    and bar.price_kijun_distance_atr >= float(expected)
                ),
                "Price–Kijun distance in ATR >= threshold.",
            ),
            ConditionSpec(
                "price_kijun_distance_atr_max",
                float,
                "ichimoku_analytics",
                lambda bar, expected, _d: (
                    bar.price_kijun_distance_atr is not None
                    and bar.price_kijun_distance_atr <= float(expected)
                ),
                "Price–Kijun distance in ATR <= threshold.",
            ),
            ConditionSpec(
                "kijun_break_bullish",
                bool,
                "ichimoku_analytics",
                lambda bar, expected, _d: bar.kijun_break_bullish == expected,
                "Bullish Kijun break on this bar.",
            ),
            ConditionSpec(
                "kijun_break_bearish",
                bool,
                "ichimoku_analytics",
                lambda bar, expected, _d: bar.kijun_break_bearish == expected,
                "Bearish Kijun break on this bar.",
            ),
            ConditionSpec(
                "kumo_orientation",
                str,
                "ichimoku_analytics",
                lambda bar, expected, _d: bar.kumo_orientation == str(expected),
                "Kumo orientation (Senkou A vs B).",
                allowed_values=("BULLISH", "BEARISH"),
            ),
            ConditionSpec(
                "kumo_twist_age_max",
                int,
                "ichimoku_analytics",
                lambda bar, expected, _d: (
                    bar.bars_since_kumo_twist is not None
                    and bar.bars_since_kumo_twist <= int(expected)
                ),
                "Bars since kumo twist <= N.",
            ),
            ConditionSpec(
                "kumo_thickness_atr_min",
                float,
                "ichimoku_analytics",
                lambda bar, expected, _d: (
                    bar.kumo_thickness_atr is not None
                    and bar.kumo_thickness_atr >= float(expected)
                ),
                "Kumo thickness in ATR >= threshold.",
            ),
            ConditionSpec(
                "kumo_thickness_atr_max",
                float,
                "ichimoku_analytics",
                lambda bar, expected, _d: (
                    bar.kumo_thickness_atr is not None
                    and bar.kumo_thickness_atr <= float(expected)
                ),
                "Kumo thickness in ATR <= threshold.",
            ),
        ]
    )

    def _kijun_retest(bar: FeatureBar, expected: ConditionValue, direction: Direction) -> bool:
        hit = (
            bar.kijun_retest_bullish
            if direction == Direction.LONG
            else bar.kijun_retest_bearish
        )
        return hit == bool(expected)

    def _kijun_bounce(bar: FeatureBar, expected: ConditionValue, direction: Direction) -> bool:
        hit = (
            bar.kijun_bounce_bullish
            if direction == Direction.LONG
            else bar.kijun_bounce_bearish
        )
        return hit == bool(expected)

    specs.extend(
        [
            ConditionSpec(
                "kijun_retest",
                bool,
                "derived",
                _kijun_retest,
                "Kijun retest in trade direction.",
            ),
            ConditionSpec(
                "kijun_bounce",
                bool,
                "derived",
                _kijun_bounce,
                "Kijun bounce in trade direction.",
            ),
        ]
    )

    # --- ppo ---
    specs.extend(
        [
            ConditionSpec(
                "ppo_above_signal",
                bool,
                "ppo",
                lambda bar, expected, _d: bar.ppo_above_signal == expected,
                "PPO above signal line.",
            ),
            ConditionSpec(
                "ppo_below_signal",
                bool,
                "ppo",
                lambda bar, expected, _d: bar.ppo_below_signal == expected,
                "PPO below signal line.",
            ),
            ConditionSpec(
                "ppo_above_zero",
                bool,
                "ppo",
                lambda bar, expected, _d: bar.ppo_above_zero == expected,
                "PPO above zero.",
            ),
            ConditionSpec(
                "ppo_below_zero",
                bool,
                "ppo",
                lambda bar, expected, _d: bar.ppo_below_zero == expected,
                "PPO below zero.",
            ),
            ConditionSpec(
                "ppo_histogram_rising",
                bool,
                "ppo",
                lambda bar, expected, _d: bar.ppo_histogram_rising == expected,
                "PPO histogram rising.",
            ),
            ConditionSpec(
                "ppo_histogram_falling",
                bool,
                "ppo",
                lambda bar, expected, _d: bar.ppo_histogram_falling == expected,
                "PPO histogram falling.",
            ),
            ConditionSpec(
                "ppo_signal_cross_bullish",
                bool,
                "ppo",
                lambda bar, expected, _d: bar.ppo_signal_cross_bullish == expected,
                "Bullish PPO/signal cross on this bar.",
            ),
            ConditionSpec(
                "ppo_signal_cross_bearish",
                bool,
                "ppo",
                lambda bar, expected, _d: bar.ppo_signal_cross_bearish == expected,
                "Bearish PPO/signal cross on this bar.",
            ),
            ConditionSpec(
                "ppo_min",
                float,
                "ppo",
                lambda bar, expected, _d: bar.ppo is not None and bar.ppo >= float(expected),
                "PPO >= threshold.",
            ),
            ConditionSpec(
                "ppo_max",
                float,
                "ppo",
                lambda bar, expected, _d: bar.ppo is not None and bar.ppo <= float(expected),
                "PPO <= threshold.",
            ),
            ConditionSpec(
                "ppo_momentum",
                str,
                "ppo",
                lambda bar, expected, _d: bar.ppo_momentum == str(expected),
                "PPO momentum bucket.",
                allowed_values=(
                    "STRONG_BULLISH",
                    "BULLISH",
                    "NEUTRAL",
                    "BEARISH",
                    "STRONG_BEARISH",
                ),
            ),
        ]
    )

    def _ppo_cross_age_max(
        bar: FeatureBar, expected: ConditionValue, direction: Direction
    ) -> bool:
        age = (
            bar.ppo_cross_age_bullish
            if direction == Direction.LONG
            else bar.ppo_cross_age_bearish
        )
        return age is not None and age <= int(expected)

    specs.append(
        ConditionSpec(
            "ppo_cross_age_max",
            int,
            "derived",
            _ppo_cross_age_max,
            "Bars since last PPO signal cross in trade direction <= N.",
        )
    )

    # --- best_cloud ---
    specs.extend(
        [
            ConditionSpec(
                "best_cloud_trend",
                str,
                "best_cloud",
                lambda bar, expected, _d: bar.best_cloud_trend == str(expected),
                "BEST Cloud trend state.",
                allowed_values=("BULLISH", "BEARISH", "NEUTRAL"),
            ),
            ConditionSpec(
                "best_cloud_bullish",
                bool,
                "best_cloud",
                lambda bar, expected, _d: bar.best_cloud_bullish == expected,
                "Price in bullish BEST Cloud regime.",
            ),
            ConditionSpec(
                "best_cloud_bearish",
                bool,
                "best_cloud",
                lambda bar, expected, _d: bar.best_cloud_bearish == expected,
                "Price in bearish BEST Cloud regime.",
            ),
            ConditionSpec(
                "best_cloud_inside",
                bool,
                "best_cloud",
                lambda bar, expected, _d: bar.best_cloud_inside == expected,
                "Price inside BEST Cloud.",
            ),
            ConditionSpec(
                "best_cloud_cross_bullish",
                bool,
                "best_cloud",
                lambda bar, expected, _d: bar.best_cloud_cross_bullish == expected,
                "Bullish BEST Cloud cross on this bar.",
            ),
            ConditionSpec(
                "best_cloud_cross_bearish",
                bool,
                "best_cloud",
                lambda bar, expected, _d: bar.best_cloud_cross_bearish == expected,
                "Bearish BEST Cloud cross on this bar.",
            ),
        ]
    )

    def _best_cloud_cross_age_max(
        bar: FeatureBar, expected: ConditionValue, direction: Direction
    ) -> bool:
        age = (
            bar.best_cloud_cross_age_bullish
            if direction == Direction.LONG
            else bar.best_cloud_cross_age_bearish
        )
        return age is not None and age <= int(expected)

    specs.append(
        ConditionSpec(
            "best_cloud_cross_age_max",
            int,
            "derived",
            _best_cloud_cross_age_max,
            "Bars since last BEST Cloud cross in trade direction <= N.",
        )
    )

    out: dict[str, ConditionSpec] = {}
    for spec in specs:
        if spec.key in out:
            raise ValueError(f"duplicate ConditionSpec key: {spec.key!r}")
        out[spec.key] = spec
    return out


CONDITION_REGISTRY: Mapping[str, ConditionSpec] = _build_registry()
