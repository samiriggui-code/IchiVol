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
    # --- Ichimoku Analytics experiments (Lab only, not live) ---
    {
        "id": "IV_EXP_A_KUMO_BO_001",
        "version": "1",
        "direction": "LONG",
        "description": "Baseline A — Kumo breakout bullish alone",
        "conditions": {"kumo_breakout_bullish": True},
        "entry": "next_open",
        "stop_atr": 1.0,
        "target_atr": 2.0,
    },
    {
        "id": "IV_EXP_B_KUMO_RVOL_001",
        "version": "1",
        "direction": "LONG",
        "description": "Baseline B — Kumo breakout + RVOL≥1.5",
        "conditions": {"kumo_breakout_bullish": True, "rvol_min": 1.5},
        "entry": "next_open",
        "stop_atr": 1.0,
        "target_atr": 2.0,
    },
    {
        "id": "IV_EXP_C_KUMO_RVOL_KIJUN_SLOPE_001",
        "version": "1",
        "direction": "LONG",
        "description": "Test C — B + Kijun slope RISING",
        "conditions": {
            "kumo_breakout_bullish": True,
            "rvol_min": 1.5,
            "kijun_slope": "RISING",
        },
        "entry": "next_open",
        "stop_atr": 1.0,
        "target_atr": 2.0,
    },
    {
        "id": "IV_EXP_D_KUMO_RVOL_KIJUN_DIST_001",
        "version": "1",
        "direction": "LONG",
        "description": "Test D — C + |price-kijun|/ATR ≤ 2 (controlled extension)",
        "conditions": {
            "kumo_breakout_bullish": True,
            "rvol_min": 1.5,
            "kijun_slope": "RISING",
            "price_kijun_distance_atr_max": 2.0,
        },
        "entry": "next_open",
        "stop_atr": 1.0,
        "target_atr": 2.0,
    },
    {
        "id": "IV_EXP_E_KUMO_RVOL_RETEST_001",
        "version": "1",
        "direction": "LONG",
        "description": "Test E — Kumo breakout + RVOL + Kijun retest",
        "conditions": {
            "kumo_breakout_bullish": True,
            "rvol_min": 1.5,
            "kijun_retest": True,
        },
        "entry": "next_open",
        "stop_atr": 1.0,
        "target_atr": 2.0,
    },
    {
        "id": "IV_EXP_F_TK_KUMO_RVOL_001",
        "version": "1",
        "direction": "LONG",
        "description": "Test F — TK cross bullish + price above Kumo + RVOL≥1.5",
        "conditions": {
            "tk_cross_bullish": True,
            "price_above_kumo": True,
            "rvol_min": 1.5,
        },
        "entry": "next_open",
        "stop_atr": 1.0,
        "target_atr": 2.0,
    },
    {
        "id": "IV_EXP_G_TK_AGE_001",
        "version": "1",
        "direction": "LONG",
        "description": "Test G — F + TK cross age ≤ 3",
        "conditions": {
            "tk_cross_bullish": True,
            "price_above_kumo": True,
            "rvol_min": 1.5,
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
    # Deduplicate by id (keep first)
    seen: set[str] = set()
    out: list[Ruleset] = []
    for raw in _BUILTIN_RAW:
        rid = raw["id"]
        if rid in seen:
            continue
        seen.add(rid)
        out.append(parse_ruleset(raw))
    return out


def get_builtin_ruleset(ruleset_id: str) -> Ruleset:
    rid = ruleset_id.strip().upper()
    for rs in list_builtin_rulesets():
        if rs.id.upper() == rid:
            return rs
    known = ", ".join(r.id for r in list_builtin_rulesets())
    raise ValueError(f"unknown ruleset {ruleset_id!r}; known: {known}")
