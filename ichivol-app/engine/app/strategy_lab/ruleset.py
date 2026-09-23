"""Declarative strategy ruleset (Strategy Lab Phase 2 + T3 DSL v3 slice 1).

A ruleset is a versioned, testable hypothesis — not a live BUY score.

T3 slice 1 — boolean composition:
  - Legacy flat ``conditions: {key: value, ...}`` ≡ ``all`` (AND), unchanged.
  - Additive nested form::

        "conditions": {
            "all": {"rvol_min": 1.5, "price_above_kumo": true},
            "any": {"bos_bullish": true, "tk_cross_bullish": true}
        }

    Match = (all leaves hold, if any) AND (at least one ``any`` leaf holds, if any).

Unknown leaf keys raise at parse time so typos cannot silently widen a study.
Evaluation is causal: bar i only sees features derived from candles[0..i].
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from app.agents.types import Direction

# Known condition keys → expected Python type (bool / int / float / str).
CONDITION_SCHEMA: dict[str, type] = {
    "price_above_kumo": bool,
    "price_below_kumo": bool,
    "tenkan_above_kijun": bool,
    "tenkan_below_kijun": bool,
    "tk_cross_bullish": bool,
    "tk_cross_bearish": bool,
    "tk_cross_age_max": int,
    "kumo_breakout_bullish": bool,
    "kumo_breakout_bearish": bool,
    "rvol_min": float,
    "rvol_max": float,
    "bos_bullish": bool,
    "bos_bearish": bool,
    "structure_bias_bullish": bool,
    "structure_bias_bearish": bool,
    "atr_percentile_min": float,
    "atr_percentile_max": float,
    "atr_expansion": bool,
    "cmf_min": float,
    "cmf_max": float,
    "rsi_min": float,
    "rsi_max": float,
    # Ichimoku Analytics (research — Lab only)
    "kijun_slope": str,  # RISING | FLAT | FALLING
    "price_kijun_distance_atr_min": float,
    "price_kijun_distance_atr_max": float,
    "kijun_break_bullish": bool,
    "kijun_break_bearish": bool,
    "kijun_retest": bool,
    "kijun_bounce": bool,
    "kumo_orientation": str,  # BULLISH | BEARISH
    "kumo_twist_age_max": int,
    "kumo_thickness_atr_min": float,
    "kumo_thickness_atr_max": float,
    # T-EXP experimental (Lab only)
    "ppo_above_signal": bool,
    "ppo_below_signal": bool,
    "ppo_above_zero": bool,
    "ppo_below_zero": bool,
    "ppo_histogram_rising": bool,
    "ppo_histogram_falling": bool,
    "ppo_signal_cross_bullish": bool,
    "ppo_signal_cross_bearish": bool,
    "ppo_cross_age_max": int,  # bars since last signal cross in trade direction
    "ppo_min": float,
    "ppo_max": float,
    "ppo_momentum": str,  # STRONG_BULLISH | BULLISH | NEUTRAL | BEARISH | STRONG_BEARISH
    "best_cloud_trend": str,  # BULLISH | BEARISH | NEUTRAL
    "best_cloud_bullish": bool,
    "best_cloud_bearish": bool,
    "best_cloud_inside": bool,
    "best_cloud_cross_bullish": bool,
    "best_cloud_cross_bearish": bool,
    "best_cloud_cross_age_max": int,  # bars since last cross in trade direction
}

CONDITION_ENUMS: dict[str, frozenset[str]] = {
    "kijun_slope": frozenset({"RISING", "FLAT", "FALLING"}),
    "kumo_orientation": frozenset({"BULLISH", "BEARISH"}),
    "ppo_momentum": frozenset(
        {"STRONG_BULLISH", "BULLISH", "NEUTRAL", "BEARISH", "STRONG_BEARISH"}
    ),
    "best_cloud_trend": frozenset({"BULLISH", "BEARISH", "NEUTRAL"}),
}

_ENTRY_MODES = frozenset({"next_open", "close_confirmation"})
_COMPOSITION_KEYS = frozenset({"all", "any"})

ConditionValue = bool | int | float | str


@dataclass(frozen=True)
class ConditionGroup:
    """Boolean composition over leaf conditions (T3).

    ``all_of`` empty → AND clause skipped (vacuous true).
    ``any_of`` empty → OR clause skipped (vacuous true).
    At least one group must be non-empty at parse time.
    """

    all_of: Mapping[str, ConditionValue] = field(default_factory=dict)
    any_of: Mapping[str, ConditionValue] = field(default_factory=dict)

    def is_legacy_flat(self) -> bool:
        return bool(self.all_of) and not self.any_of


@dataclass(frozen=True)
class Ruleset:
    id: str
    direction: Direction
    condition_group: ConditionGroup
    entry: str = "next_open"
    stop_atr: float = 1.0
    target_atr: float = 2.0
    symbol: str | None = None
    """Optional intended symbol (documentation / validation hint)."""
    timeframe: str | None = None
    """Optional intended timeframe."""
    version: str = "1"
    description: str = ""
    meta: Mapping[str, Any] = field(default_factory=dict)

    @property
    def conditions(self) -> Mapping[str, ConditionValue]:
        """Legacy flat view = ``all_of`` leaves (catalog / ablation / optimizer)."""
        return self.condition_group.all_of

    def to_dict(self) -> dict[str, Any]:
        group = self.condition_group
        if group.is_legacy_flat():
            conditions: dict[str, Any] = dict(group.all_of)
        elif group.all_of and group.any_of:
            conditions = {"all": dict(group.all_of), "any": dict(group.any_of)}
        elif group.any_of:
            conditions = {"any": dict(group.any_of)}
        else:
            conditions = {"all": dict(group.all_of)}
        return {
            "id": self.id,
            "version": self.version,
            "direction": self.direction.value,
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "description": self.description,
            "conditions": conditions,
            "entry": self.entry,
            "stop_atr": self.stop_atr,
            "target_atr": self.target_atr,
            "meta": dict(self.meta),
        }


def _coerce_leaf(key_s: str, value: Any) -> ConditionValue:
    if key_s not in CONDITION_SCHEMA:
        known = ", ".join(sorted(CONDITION_SCHEMA))
        raise ValueError(f"unknown condition {key_s!r}; known: {known}")
    expected = CONDITION_SCHEMA[key_s]
    if expected is bool:
        if not isinstance(value, bool):
            raise ValueError(f"condition {key_s} must be bool")
        return value
    if expected is int:
        if isinstance(value, bool) or not isinstance(value, int):
            raise ValueError(f"condition {key_s} must be int")
        if value < 0:
            raise ValueError(f"condition {key_s} must be >= 0")
        return value
    if expected is str:
        if not isinstance(value, str):
            raise ValueError(f"condition {key_s} must be str")
        allowed = CONDITION_ENUMS.get(key_s)
        upper = value.strip().upper()
        if allowed is not None and upper not in allowed:
            raise ValueError(f"condition {key_s} must be one of {sorted(allowed)}")
        return upper
    # float
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"condition {key_s} must be number")
    return float(value)


def _parse_leaf_map(raw: Any, *, label: str) -> dict[str, ConditionValue]:
    if not isinstance(raw, Mapping):
        raise ValueError(f"ruleset.conditions.{label} must be an object")
    if not raw:
        return {}
    out: dict[str, ConditionValue] = {}
    for key, value in raw.items():
        key_s = str(key)
        if key_s in _COMPOSITION_KEYS:
            raise ValueError(
                f"nested all/any under conditions.{label} is not supported yet"
            )
        out[key_s] = _coerce_leaf(key_s, value)
    return out


def _parse_condition_group(conditions_raw: Mapping[str, Any]) -> ConditionGroup:
    keys = {str(k) for k in conditions_raw.keys()}
    if keys & _COMPOSITION_KEYS:
        leftover = keys - _COMPOSITION_KEYS
        if leftover:
            raise ValueError(
                "cannot mix leaf conditions with all/any groups; "
                f"unexpected keys: {sorted(leftover)}"
            )
        all_of = (
            _parse_leaf_map(conditions_raw["all"], label="all")
            if "all" in conditions_raw
            else {}
        )
        any_of = (
            _parse_leaf_map(conditions_raw["any"], label="any")
            if "any" in conditions_raw
            else {}
        )
        if not all_of and not any_of:
            raise ValueError("ruleset.conditions all/any must include at least one leaf")
        return ConditionGroup(all_of=all_of, any_of=any_of)

    # Legacy flat AND.
    all_of = _parse_leaf_map(conditions_raw, label="(flat)")
    if not all_of:
        raise ValueError("ruleset.conditions must be a non-empty object")
    return ConditionGroup(all_of=all_of, any_of={})


def parse_ruleset(raw: Mapping[str, Any]) -> Ruleset:
    """Parse and validate a ruleset dict. Raises ValueError on bad input."""
    rid = str(raw.get("id") or "").strip()
    if not rid:
        raise ValueError("ruleset.id is required")

    direction_raw = str(raw.get("direction") or "").upper()
    try:
        direction = Direction(direction_raw)
    except ValueError as exc:
        raise ValueError("ruleset.direction must be LONG or SHORT") from exc
    if direction == Direction.NEUTRAL:
        raise ValueError("ruleset.direction must be LONG or SHORT")

    conditions_raw = raw.get("conditions")
    if not isinstance(conditions_raw, Mapping) or not conditions_raw:
        raise ValueError("ruleset.conditions must be a non-empty object")

    condition_group = _parse_condition_group(conditions_raw)

    entry = str(raw.get("entry") or "next_open")
    if entry not in _ENTRY_MODES:
        raise ValueError(f"entry must be one of {sorted(_ENTRY_MODES)}")

    stop_atr = float(raw.get("stop_atr", 1.0))
    target_atr = float(raw.get("target_atr", 2.0))
    if stop_atr <= 0 or target_atr <= 0:
        raise ValueError("stop_atr and target_atr must be > 0")

    symbol = raw.get("symbol")
    timeframe = raw.get("timeframe")
    return Ruleset(
        id=rid,
        direction=direction,
        condition_group=condition_group,
        entry=entry,
        stop_atr=stop_atr,
        target_atr=target_atr,
        symbol=str(symbol).upper() if symbol else None,
        timeframe=str(timeframe) if timeframe else None,
        version=str(raw.get("version") or "1"),
        description=str(raw.get("description") or ""),
        meta=dict(raw.get("meta") or {}),
    )
