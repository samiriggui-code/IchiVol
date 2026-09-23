"""Declarative strategy ruleset (Strategy Lab Phase 2 + T3 DSL v3).

A ruleset is a versioned, testable hypothesis — not a live BUY score.

T3 slice 1 — boolean composition:
  - Legacy flat ``conditions: {key: value, ...}`` ≡ ``all`` (AND), unchanged.
  - Additive nested form::

        "conditions": {
            "all": {"rvol_min": 1.5, "price_above_kumo": true},
            "any": {"bos_bullish": true, "tk_cross_bullish": true}
        }

    Match = (all leaves hold, if any) AND (at least one ``any`` leaf holds, if any).

T3 slice 2 — optional ``exit`` block (ATR SL/TP stay top-level)::

    "exit": {
        "max_hold_bars": 48,
        "conditions": {"any": {"tk_cross_bearish": true}}
    }

Unknown leaf keys raise at parse time so typos cannot silently widen a study.
Evaluation is causal: bar i only sees features derived from candles[0..i].
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from app.agents.types import Direction
from app.strategy_lab.conditions import CONDITION_REGISTRY
from app.strategy_lab.stop_trail import TrailSpec

# Derived from CONDITION_REGISTRY (T3c) — keep name for optimization.py / api/rulesets.py.
CONDITION_SCHEMA: dict[str, type] = {
    k: spec.value_type for k, spec in CONDITION_REGISTRY.items()
}

CONDITION_ENUMS: dict[str, frozenset[str]] = {
    k: frozenset(spec.allowed_values)
    for k, spec in CONDITION_REGISTRY.items()
    if spec.allowed_values is not None
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
class ExitSpec:
    """Optional lab exit beyond ATR stop/target (T3 slice 2 + T0-MANAGE-a).

    Empty / omitted ≡ today's ATR-only behaviour.
    ``condition_group`` None = no signal exit.
    ``trail`` None = fixed stop at entry (legacy).
    """

    max_hold_bars: int | None = None
    condition_group: ConditionGroup | None = None
    trail: TrailSpec | None = None

    def is_empty(self) -> bool:
        return (
            self.max_hold_bars is None
            and self.condition_group is None
            and (self.trail is None or self.trail.is_empty())
        )


@dataclass(frozen=True)
class Ruleset:
    id: str
    direction: Direction
    condition_group: ConditionGroup
    entry: str = "next_open"
    stop_atr: float = 1.0
    target_atr: float = 2.0
    exit: ExitSpec = field(default_factory=ExitSpec)
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
        out: dict[str, Any] = {
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
        if not self.exit.is_empty():
            exit_payload: dict[str, Any] = {}
            if self.exit.max_hold_bars is not None:
                exit_payload["max_hold_bars"] = self.exit.max_hold_bars
            if self.exit.condition_group is not None:
                eg = self.exit.condition_group
                if eg.is_legacy_flat():
                    exit_payload["conditions"] = dict(eg.all_of)
                elif eg.all_of and eg.any_of:
                    exit_payload["conditions"] = {
                        "all": dict(eg.all_of),
                        "any": dict(eg.any_of),
                    }
                elif eg.any_of:
                    exit_payload["conditions"] = {"any": dict(eg.any_of)}
                else:
                    exit_payload["conditions"] = {"all": dict(eg.all_of)}
            if self.exit.trail is not None and not self.exit.trail.is_empty():
                trail_payload: dict[str, Any] = {}
                if self.exit.trail.breakeven_at_r is not None:
                    trail_payload["breakeven_at_r"] = self.exit.trail.breakeven_at_r
                if self.exit.trail.atr_trail_mult is not None:
                    trail_payload["atr_trail_mult"] = self.exit.trail.atr_trail_mult
                exit_payload["trail"] = trail_payload
            out["exit"] = exit_payload
        return out


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


_EXIT_KEYS = frozenset({"max_hold_bars", "conditions", "trail"})
_TRAIL_KEYS = frozenset({"breakeven_at_r", "atr_trail_mult"})


def _parse_trail_spec(raw: Any) -> TrailSpec:
    if not isinstance(raw, Mapping):
        raise ValueError("ruleset.exit.trail must be an object")
    if not raw:
        raise ValueError("ruleset.exit.trail must set breakeven_at_r and/or atr_trail_mult")
    keys = {str(k) for k in raw.keys()}
    unknown = keys - _TRAIL_KEYS
    if unknown:
        raise ValueError(f"unknown ruleset.exit.trail keys: {sorted(unknown)}")

    breakeven: float | None = None
    if "breakeven_at_r" in raw:
        be = raw["breakeven_at_r"]
        if isinstance(be, bool) or not isinstance(be, (int, float)) or float(be) <= 0:
            raise ValueError("ruleset.exit.trail.breakeven_at_r must be a number > 0")
        breakeven = float(be)

    atr_mult: float | None = None
    if "atr_trail_mult" in raw:
        am = raw["atr_trail_mult"]
        if isinstance(am, bool) or not isinstance(am, (int, float)) or float(am) <= 0:
            raise ValueError("ruleset.exit.trail.atr_trail_mult must be a number > 0")
        atr_mult = float(am)

    if breakeven is None and atr_mult is None:
        raise ValueError("ruleset.exit.trail must set breakeven_at_r and/or atr_trail_mult")
    return TrailSpec(breakeven_at_r=breakeven, atr_trail_mult=atr_mult)


def _parse_exit_spec(raw: Any) -> ExitSpec:
    if raw is None:
        return ExitSpec()
    if not isinstance(raw, Mapping):
        raise ValueError("ruleset.exit must be an object")
    if not raw:
        return ExitSpec()
    # ATR levels stay top-level — reject dual source before generic unknown.
    for banned in ("stop_atr", "target_atr"):
        if banned in raw:
            raise ValueError(
                f"ruleset.exit must not contain {banned}; keep it top-level"
            )
    keys = {str(k) for k in raw.keys()}
    unknown = keys - _EXIT_KEYS
    if unknown:
        raise ValueError(f"unknown ruleset.exit keys: {sorted(unknown)}")

    max_hold: int | None = None
    if "max_hold_bars" in raw:
        mh = raw["max_hold_bars"]
        if isinstance(mh, bool) or not isinstance(mh, int) or mh < 1:
            raise ValueError("ruleset.exit.max_hold_bars must be an int >= 1")
        max_hold = mh

    cond_group: ConditionGroup | None = None
    if "conditions" in raw:
        cond_raw = raw["conditions"]
        if not isinstance(cond_raw, Mapping) or not cond_raw:
            raise ValueError("ruleset.exit.conditions must be a non-empty object")
        cond_group = _parse_condition_group(cond_raw)

    trail: TrailSpec | None = None
    if "trail" in raw:
        trail = _parse_trail_spec(raw["trail"])

    if max_hold is None and cond_group is None and trail is None:
        return ExitSpec()
    return ExitSpec(max_hold_bars=max_hold, condition_group=cond_group, trail=trail)


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

    exit_spec = _parse_exit_spec(raw.get("exit"))

    symbol = raw.get("symbol")
    timeframe = raw.get("timeframe")
    return Ruleset(
        id=rid,
        direction=direction,
        condition_group=condition_group,
        entry=entry,
        stop_atr=stop_atr,
        target_atr=target_atr,
        exit=exit_spec,
        symbol=str(symbol).upper() if symbol else None,
        timeframe=str(timeframe) if timeframe else None,
        version=str(raw.get("version") or "1"),
        description=str(raw.get("description") or ""),
        meta=dict(raw.get("meta") or {}),
    )
