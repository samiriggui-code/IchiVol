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
                "choch_bullish",
                bool,
                "structure",
                lambda bar, expected, _d: bar.choch_bullish == expected,
                "EXPERIMENTAL (T9b/Lab) — Bullish CHoCH (break against bearish bias). Not read by decision pipeline yet.",
            ),
            ConditionSpec(
                "choch_bearish",
                bool,
                "structure",
                lambda bar, expected, _d: bar.choch_bearish == expected,
                "EXPERIMENTAL (T9b/Lab) — Bearish CHoCH (break against bullish bias). Not read by decision pipeline yet.",
            ),
            ConditionSpec(
                "break_quality",
                str,
                "structure",
                lambda bar, expected, _d: bar.break_quality == expected,
                "EXPERIMENTAL (T9b/Lab) — Structure break quality: wick | close | confirmed. Not read by decision pipeline yet.",
                allowed_values=("wick", "close", "confirmed"),
            ),
            ConditionSpec(
                "impulse_bullish",
                bool,
                "structure",
                lambda bar, expected, _d: bar.impulse_bullish == expected,
                "EXPERIMENTAL (T9c/Lab) — Bullish pivot-to-pivot impulse this bar. Not read by decision pipeline yet.",
            ),
            ConditionSpec(
                "impulse_bearish",
                bool,
                "structure",
                lambda bar, expected, _d: bar.impulse_bearish == expected,
                "EXPERIMENTAL (T9c/Lab) — Bearish pivot-to-pivot impulse this bar. Not read by decision pipeline yet.",
            ),
            ConditionSpec(
                "fvg_bullish",
                bool,
                "structure",
                lambda bar, expected, _d: bar.fvg_bullish == expected,
                "EXPERIMENTAL (T9d/Lab) — Bullish FVG discovered this bar. Not read by decision pipeline yet.",
            ),
            ConditionSpec(
                "fvg_bearish",
                bool,
                "structure",
                lambda bar, expected, _d: bar.fvg_bearish == expected,
                "EXPERIMENTAL (T9d/Lab) — Bearish FVG discovered this bar. Not read by decision pipeline yet.",
            ),
            ConditionSpec(
                "fvg_active",
                bool,
                "structure",
                lambda bar, expected, _d: bar.fvg_active == expected,
                "EXPERIMENTAL (T9d/Lab) — At least one open/partial FVG is live. Not read by decision pipeline yet.",
            ),
            ConditionSpec(
                "fvg_status",
                str,
                "structure",
                lambda bar, expected, _d: bar.fvg_status == expected,
                "EXPERIMENTAL (T9f/Lab) — FVG event status this bar. Not read by decision pipeline yet.",
                allowed_values=("open", "partial", "filled", "invalidated"),
            ),
            ConditionSpec(
                "impulse_displacement_atr_min",
                float,
                "structure",
                lambda bar, expected, _d: (
                    bar.impulse_displacement_atr is not None
                    and bar.impulse_displacement_atr >= float(expected)
                ),
                "EXPERIMENTAL (T9f/Lab) — Impulse displacement_atr >= threshold this bar.",
            ),
            ConditionSpec(
                "fib_confluence",
                bool,
                "structure",
                lambda bar, expected, _d: bar.fib_confluence == expected,
                "EXPERIMENTAL (T9f/Lab) — Close near a Fib level (impulse-anchored). Not read by decision pipeline yet.",
            ),
            ConditionSpec(
                "fib_key_confluence",
                bool,
                "structure",
                lambda bar, expected, _d: bar.fib_key_confluence == expected,
                "EXPERIMENTAL (T9f/Lab) — Close near a key Fib (0.5/0.618/0.786).",
            ),
            ConditionSpec(
                "fib_impulse_up",
                bool,
                "structure",
                lambda bar, expected, _d: bar.fib_impulse_up == expected,
                "EXPERIMENTAL (T9f/Lab) — Fib anchored on bullish (up) impulse.",
            ),
            ConditionSpec(
                "fib_impulse_down",
                bool,
                "structure",
                lambda bar, expected, _d: bar.fib_impulse_down == expected,
                "EXPERIMENTAL (T9f/Lab) — Fib anchored on bearish (down) impulse.",
            ),
            ConditionSpec(
                "fib_anchor_impulse",
                bool,
                "structure",
                lambda bar, expected, _d: bar.fib_anchor_impulse == expected,
                "EXPERIMENTAL (T9f/Lab) — Fib levels derived from a qualified ImpulseEvent.",
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

    # --- T12b Lab ↔ live parity (ADD-ONLY) ---
    specs.extend(
        [
            ConditionSpec(
                "chikou_state",
                str,
                "ichimoku",
                lambda bar, expected, _d: bar.chikou_state == expected,
                "T12b — Ichimoku chikou_state (same as live agent). Lab observation.",
                allowed_values=(
                    "CLEAR_BULLISH",
                    "CLEAR_BEARISH",
                    "OBSTRUCTED",
                    "UNKNOWN",
                ),
            ),
            ConditionSpec(
                "future_kumo",
                str,
                "ichimoku",
                lambda bar, expected, _d: bar.future_kumo == expected,
                "T12b — Ichimoku future_kumo (same as live). Lab observation.",
                allowed_values=("BULLISH", "BEARISH", "NONE", "UNKNOWN"),
            ),
            ConditionSpec(
                "ichimoku_direction",
                str,
                "ichimoku",
                lambda bar, expected, _d: bar.ichimoku_direction == expected,
                "T12b — Ichimoku agent direction (reuse ichimoku_agent). Lab observation.",
                allowed_values=("LONG", "SHORT", "NEUTRAL"),
            ),
            ConditionSpec(
                "ichimoku_score_min",
                float,
                "ichimoku",
                lambda bar, expected, _d: bar.ichimoku_score is not None
                and bar.ichimoku_score >= float(expected),
                "T12b — Ichimoku score >= threshold. Lab observation.",
            ),
            ConditionSpec(
                "donchian_breakout",
                str,
                "donchian",
                lambda bar, expected, _d: bar.donchian_breakout == expected,
                "T12b — Donchian breakout (same as live). Lab observation.",
                allowed_values=("UP", "DOWN", "INSIDE", "UNKNOWN"),
            ),
            ConditionSpec(
                "adx_min",
                float,
                "adx",
                lambda bar, expected, _d: bar.adx is not None and bar.adx >= float(expected),
                "T12b — ADX >= threshold. Lab observation.",
            ),
            ConditionSpec(
                "regime_trending",
                bool,
                "adx",
                lambda bar, expected, _d: bar.regime_trending == expected,
                "T12b — classify_regimes TRENDING. Lab observation.",
            ),
            ConditionSpec(
                "regime_ranging",
                bool,
                "adx",
                lambda bar, expected, _d: bar.regime_ranging == expected,
                "T12b — classify_regimes RANGING. Lab observation.",
            ),
            ConditionSpec(
                "regime_high_volatility",
                bool,
                "atr",
                lambda bar, expected, _d: bar.regime_high_volatility == expected,
                "T12b — HIGH_VOLATILITY tag. Lab observation.",
            ),
            ConditionSpec(
                "regime_low_volatility",
                bool,
                "atr",
                lambda bar, expected, _d: bar.regime_low_volatility == expected,
                "T12b — LOW_VOLATILITY tag. Lab observation.",
            ),
            ConditionSpec(
                "regime_normal_volatility",
                bool,
                "atr",
                lambda bar, expected, _d: bar.regime_normal_volatility == expected,
                "T12b — NORMAL_VOLATILITY tag. Lab observation.",
            ),
            ConditionSpec(
                "regime_bull",
                bool,
                "adx",
                lambda bar, expected, _d: bar.regime_bull == expected,
                "T12b — BULL direction tag. Lab observation.",
            ),
            ConditionSpec(
                "regime_bear",
                bool,
                "adx",
                lambda bar, expected, _d: bar.regime_bear == expected,
                "T12b — BEAR direction tag. Lab observation.",
            ),
            ConditionSpec(
                "regime_sideways",
                bool,
                "adx",
                lambda bar, expected, _d: bar.regime_sideways == expected,
                "T12b — SIDEWAYS direction tag. Lab observation.",
            ),
            ConditionSpec(
                "regime_stage_pass",
                str,
                "derived",
                lambda bar, expected, _d: bar.regime_stage_pass == expected,
                "T12b — same verdict as pipeline _regime_stage.status. Lab observation.",
                allowed_values=("pass", "fail", "watch", "pending", "skip"),
            ),
            ConditionSpec(
                "above_vwap",
                bool,
                "location",
                lambda bar, expected, _d: bar.above_vwap == expected,
                "T12b — price above VWAP. Lab observation.",
            ),
            ConditionSpec(
                "below_vwap",
                bool,
                "location",
                lambda bar, expected, _d: bar.below_vwap == expected,
                "T12b — price at/below VWAP. Lab observation.",
            ),
            ConditionSpec(
                "avwap_aligned",
                bool,
                "location",
                lambda bar, expected, _d: bar.avwap_aligned == expected,
                "T12b — AVWAP side aligned with ichimoku direction. Lab observation.",
            ),
            ConditionSpec(
                "avwap_opposed",
                bool,
                "location",
                lambda bar, expected, _d: bar.avwap_opposed == expected,
                "T12b — AVWAP side opposed to ichimoku direction. Lab observation.",
            ),
            ConditionSpec(
                "inside_value_area",
                bool,
                "location",
                lambda bar, expected, _d: bar.inside_value_area == expected,
                "T12b — inside value area (vs trade direction). Lab observation.",
            ),
            ConditionSpec(
                "beyond_value_area",
                bool,
                "location",
                lambda bar, expected, _d: bar.beyond_value_area == expected,
                "T12b — beyond value area in trade direction. Lab observation.",
            ),
            ConditionSpec(
                "wrong_side_value_area",
                bool,
                "location",
                lambda bar, expected, _d: bar.wrong_side_value_area == expected,
                "T12b — wrong side of value area. Lab observation.",
            ),
            ConditionSpec(
                "congestion_hvn",
                bool,
                "location",
                lambda bar, expected, _d: bar.congestion_hvn == expected,
                "T12b — HVN congestion. Lab observation.",
            ),
            ConditionSpec(
                "location_stage_pass",
                str,
                "derived",
                lambda bar, expected, _d: bar.location_stage_pass == expected,
                "T12b — same verdict as pipeline _location_stage.status. Lab observation.",
                allowed_values=("pass", "fail", "watch", "pending", "skip"),
            ),
            ConditionSpec(
                "cvd_bias",
                str,
                "cvd",
                lambda bar, expected, _d: bar.cvd_bias == expected,
                "T12b — CVD bias. Lab observation.",
                allowed_values=("BULLISH", "BEARISH", "NEUTRAL", "UNKNOWN"),
            ),
            ConditionSpec(
                "rvol_faible",
                bool,
                "rvol",
                lambda bar, expected, _d: bar.rvol_faible == expected,
                "T12b — RVOL < 0.7 (Lab band). Lab observation.",
            ),
            ConditionSpec(
                "rvol_normal",
                bool,
                "rvol",
                lambda bar, expected, _d: bar.rvol_normal == expected,
                "T12b — RVOL 0.7–1.2 (Lab band). Lab observation.",
            ),
            ConditionSpec(
                "rvol_eleve",
                bool,
                "rvol",
                lambda bar, expected, _d: bar.rvol_eleve == expected,
                "T12b — RVOL 1.2–1.5 (Lab band). Lab observation.",
            ),
            ConditionSpec(
                "rvol_fort",
                bool,
                "rvol",
                lambda bar, expected, _d: bar.rvol_fort == expected,
                "T12b — RVOL 1.5–2 (Lab band). Lab observation.",
            ),
            ConditionSpec(
                "rvol_extreme",
                bool,
                "rvol",
                lambda bar, expected, _d: bar.rvol_extreme == expected,
                "T12b — RVOL > 2 (Lab band). Lab observation.",
            ),
            ConditionSpec(
                "participation_stage_pass",
                str,
                "derived",
                lambda bar, expected, _d: bar.participation_stage_pass == expected,
                "T12b — same verdict as pipeline _participation_stage.status. Lab observation.",
                allowed_values=("pass", "fail", "watch", "pending", "skip"),
            ),
        ]
    )

    out: dict[str, ConditionSpec] = {}
    for spec in specs:
        if spec.key in out:
            raise ValueError(f"duplicate ConditionSpec key: {spec.key!r}")
        out[spec.key] = spec
    return out


CONDITION_REGISTRY: Mapping[str, ConditionSpec] = _build_registry()
