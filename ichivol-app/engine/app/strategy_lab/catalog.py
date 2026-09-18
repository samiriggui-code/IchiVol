"""Built-in example rulesets — hypotheses to measure, not production signals."""

from __future__ import annotations

from app.strategy_lab.ruleset import Ruleset, parse_ruleset

_BUILTIN_RAW: list[dict] = [
    {
        "id": "IV_ICHIMOKU_RVOL_LONG_001",
        "version": "1",
        "direction": "LONG",
        "description": "Price above kumo + Tenkan>Kijun + recent bullish TK + RVOL≥1.5",
        "conditions": {
            "price_above_kumo": True,
            "tenkan_above_kijun": True,
            "tk_cross_age_max": 3,
            "rvol_min": 1.5,
        },
        "entry": "next_open",
        "stop_atr": 1.0,
        "target_atr": 2.0,
    },
    {
        "id": "IV_ICHIMOKU_ONLY_LONG_001",
        "version": "1",
        "direction": "LONG",
        "description": "Ichimoku structure alone (ablation A vs RVOL filter)",
        "conditions": {
            "price_above_kumo": True,
            "tenkan_above_kijun": True,
            "tk_cross_age_max": 3,
        },
        "entry": "next_open",
        "stop_atr": 1.0,
        "target_atr": 2.0,
    },
    {
        "id": "IV_ICHIMOKU_RVOL_BOS_LONG_001",
        "version": "1",
        "direction": "LONG",
        "description": "Ichimoku + RVOL + bullish BOS (structure break)",
        "conditions": {
            "price_above_kumo": True,
            "tenkan_above_kijun": True,
            "tk_cross_age_max": 3,
            "rvol_min": 1.5,
            "bos_bullish": True,
        },
        "entry": "next_open",
        "stop_atr": 1.0,
        "target_atr": 2.0,
    },
    {
        "id": "IV_KUMO_BREAKOUT_RVOL_LONG_001",
        "version": "1",
        "direction": "LONG",
        "description": "Kumo breakout bullish + RVOL≥1.5",
        "conditions": {
            "kumo_breakout_bullish": True,
            "rvol_min": 1.5,
        },
        "entry": "next_open",
        "stop_atr": 1.0,
        "target_atr": 2.0,
    },
]


def list_builtin_rulesets() -> list[Ruleset]:
    return [parse_ruleset(raw) for raw in _BUILTIN_RAW]


def get_builtin_ruleset(ruleset_id: str) -> Ruleset:
    rid = ruleset_id.strip().upper()
    for rs in list_builtin_rulesets():
        if rs.id.upper() == rid:
            return rs
    known = ", ".join(r.id for r in list_builtin_rulesets())
    raise ValueError(f"unknown ruleset {ruleset_id!r}; known: {known}")
