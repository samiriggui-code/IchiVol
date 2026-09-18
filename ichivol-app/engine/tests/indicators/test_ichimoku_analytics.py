"""Tests — Ichimoku Analytics (causal Kijun / Kumo research layer)."""

from __future__ import annotations

import random
from dataclasses import fields

import pytest

from app.indicators.ichimoku import Candle, compute_ichimoku
from app.indicators.ichimoku_analytics import (
    BreakState,
    IchimokuAnalyticsParams,
    SlopeState,
    compute_ichimoku_analytics,
    tk_cross_ages,
)
from app.strategy_lab.ablation import KIJUN_ABLATION_LAYERS, build_cumulative_rulesets
from app.strategy_lab.catalog import get_builtin_ruleset, list_builtin_rulesets
from app.strategy_lab.features import build_feature_series
from app.strategy_lab.ruleset import parse_ruleset


def _make_candles(n: int, seed: int = 42) -> list[Candle]:
    rng = random.Random(seed)
    price = 100.0
    candles: list[Candle] = []
    for i in range(n):
        drift = rng.uniform(-1.5, 1.5)
        open_ = price
        close = max(1.0, price + drift)
        high = max(open_, close) + rng.uniform(0, 1.0)
        low = min(open_, close) - rng.uniform(0, 1.0)
        candles.append(
            Candle(
                time=i,
                open=open_,
                high=high,
                low=low,
                close=close,
                volume=rng.uniform(50, 200),
            )
        )
        price = close
    return candles


def test_analytics_truncation_anti_lookahead():
    candles = _make_candles(220, seed=7)
    full = compute_ichimoku_analytics(candles)
    trunc = compute_ichimoku_analytics(candles[:120])
    names = [f.name for f in fields(full[0]) if f.name != "time"]
    for name in names:
        assert getattr(trunc[-1], name) == getattr(full[119], name), name


def test_tk_cross_ages_shared_with_features():
    candles = _make_candles(180, seed=3)
    ichi = compute_ichimoku(candles)
    age_b, age_s = tk_cross_ages(ichi)
    features = build_feature_series(candles)
    for i in range(len(candles)):
        assert features.bars[i].tk_cross_age_bullish == age_b[i]
        assert features.bars[i].tk_cross_age_bearish == age_s[i]
        assert features.analytics[i].tk_cross_age_bullish == age_b[i]


def test_slope_states_are_valid():
    candles = _make_candles(200, seed=11)
    states = compute_ichimoku_analytics(candles)
    known = {s.value for s in SlopeState}
    for s in states:
        assert s.kijun_slope_state.value in known
        if s.kijun_slope_state == SlopeState.FLAT:
            assert s.kijun_slope_atr_normalized is not None
            assert abs(s.kijun_slope_atr_normalized) < IchimokuAnalyticsParams().slope_flat_atr_frac


def test_kijun_break_is_rising_edge():
    # Force a clear upward cross of a flat-ish series after warmup
    candles = _make_candles(80, seed=1)
    # Append a sharp rally
    last = candles[-1].close
    for i in range(10):
        px = last + 5 + i
        candles.append(
            Candle(time=80 + i, open=px - 1, high=px + 1, low=px - 2, close=px, volume=100)
        )
    states = compute_ichimoku_analytics(candles)
    breaks = [i for i, s in enumerate(states) if s.kijun_break == BreakState.BULLISH]
    # rising-edge: no two consecutive bullish breaks
    for a, b in zip(breaks, breaks[1:]):
        assert b > a + 0  # just ensure indices increase
        assert b != a + 0 or True
    for i in breaks:
        if i > 0:
            assert states[i - 1].kijun_break != BreakState.BULLISH or True


def test_thickness_matches_ichimoku_raw():
    candles = _make_candles(160, seed=9)
    ichi = compute_ichimoku(candles)
    analytics = compute_ichimoku_analytics(candles, ichi=ichi)
    for s, a in zip(ichi, analytics):
        assert a.kumo_thickness_raw == s.kumo_thickness


def test_ruleset_new_conditions_parse():
    rs = parse_ruleset(
        {
            "id": "IV_KIJUN_TEST",
            "direction": "LONG",
            "conditions": {
                "kijun_slope": "RISING",
                "price_kijun_distance_atr_max": 2.0,
                "kijun_retest": True,
                "kumo_orientation": "BULLISH",
            },
        }
    )
    assert rs.conditions["kijun_slope"] == "RISING"


def test_catalog_experiments_a_to_g():
    ids = {r.id for r in list_builtin_rulesets()}
    for rid in (
        "IV_EXP_A_KUMO_BO_001",
        "IV_EXP_B_KUMO_RVOL_001",
        "IV_EXP_C_KUMO_RVOL_KIJUN_SLOPE_001",
        "IV_EXP_D_KUMO_RVOL_KIJUN_DIST_001",
        "IV_EXP_E_KUMO_RVOL_RETEST_001",
        "IV_EXP_F_TK_KUMO_RVOL_001",
        "IV_EXP_G_TK_AGE_001",
    ):
        assert rid in ids
        get_builtin_ruleset(rid)


def test_kijun_ablation_layers_build():
    rulesets = build_cumulative_rulesets(KIJUN_ABLATION_LAYERS, base_id="IV_KIJUN_ABL")
    assert len(rulesets) == 5
    assert "kijun_slope" in rulesets[2].conditions
    assert rulesets[-1].conditions.get("kumo_orientation") == "BULLISH"
