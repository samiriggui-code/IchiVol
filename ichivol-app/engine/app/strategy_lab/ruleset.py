"""Declarative strategy ruleset (Strategy Lab Phase 2).

A ruleset is a versioned, testable hypothesis — not a live BUY score.

Example::

    {
      "id": "IV_DEMO_LONG_001",
      "direction": "LONG",
      "conditions": {
        "price_above_kumo": true,
        "tenkan_above_kijun": true,
        "tk_cross_age_max": 3,
        "rvol_min": 1.5
      },
      "entry": "next_open",
      "stop_atr": 1.0,
      "target_atr": 2.0
    }

Conditions are AND-combined. Unknown keys raise at parse time so typos
cannot silently widen a study. Evaluation is causal: bar i only sees
features derived from candles[0..i].
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from app.agents.types import Direction

# Known condition keys → expected Python type (bool / int / float).
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
}

_ENTRY_MODES = frozenset({"next_open", "close_confirmation"})


@dataclass(frozen=True)
class Ruleset:
    id: str
    direction: Direction
    conditions: Mapping[str, bool | int | float]
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

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "version": self.version,
            "direction": self.direction.value,
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "description": self.description,
            "conditions": dict(self.conditions),
            "entry": self.entry,
            "stop_atr": self.stop_atr,
            "target_atr": self.target_atr,
            "meta": dict(self.meta),
        }


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

    conditions: dict[str, bool | int | float] = {}
    for key, value in conditions_raw.items():
        key_s = str(key)
        if key_s not in CONDITION_SCHEMA:
            known = ", ".join(sorted(CONDITION_SCHEMA))
            raise ValueError(f"unknown condition {key_s!r}; known: {known}")
        expected = CONDITION_SCHEMA[key_s]
        if expected is bool:
            if not isinstance(value, bool):
                raise ValueError(f"condition {key_s} must be bool")
            conditions[key_s] = value
        elif expected is int:
            if isinstance(value, bool) or not isinstance(value, int):
                raise ValueError(f"condition {key_s} must be int")
            if value < 0:
                raise ValueError(f"condition {key_s} must be >= 0")
            conditions[key_s] = value
        else:  # float
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise ValueError(f"condition {key_s} must be number")
            conditions[key_s] = float(value)

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
        conditions=conditions,
        entry=entry,
        stop_atr=stop_atr,
        target_atr=target_atr,
        symbol=str(symbol).upper() if symbol else None,
        timeframe=str(timeframe) if timeframe else None,
        version=str(raw.get("version") or "1"),
        description=str(raw.get("description") or ""),
        meta=dict(raw.get("meta") or {}),
    )
