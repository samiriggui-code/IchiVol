"""Tests — Strategy Lab Phase 2 Rules Engine + T3 any/all composition."""

from __future__ import annotations

import pytest

from app.indicators.ichimoku import Candle
from app.strategy_lab.catalog import get_builtin_ruleset, list_builtin_rulesets
from app.strategy_lab.evaluator import bar_matches, extract_ruleset_signals, matches_mask
from app.strategy_lab.features import FeatureBar, build_feature_series
from app.strategy_lab.ruleset import parse_ruleset
from app.strategy_lab.run_ruleset import study_ruleset_on_candles


def _c(t: int, o: float, h: float, l: float, c: float, v: float = 100.0) -> Candle:
    return Candle(time=t, open=o, high=h, low=l, close=c, volume=v)


def _bare_bar(**overrides) -> FeatureBar:
    base = dict(
        index=0,
        time=0,
        price_above_kumo=False,
        price_below_kumo=False,
        tenkan_above_kijun=False,
        tenkan_below_kijun=False,
        tk_cross_bullish=False,
        tk_cross_bearish=False,
        tk_cross_age_bullish=None,
        tk_cross_age_bearish=None,
        kumo_breakout_bullish=False,
        kumo_breakout_bearish=False,
        rvol=1.0,
        bos_bullish=False,
        bos_bearish=False,
        structure_bias_bullish=False,
        structure_bias_bearish=False,
        atr=1.0,
        atr_percentile=0.5,
        atr_expansion=False,
        cmf=None,
        rsi=None,
        kijun_slope_state="FLAT",
        kijun_slope_atr_normalized=None,
        price_kijun_distance_atr=None,
        kijun_break_bullish=False,
        kijun_break_bearish=False,
        kijun_retest_bullish=False,
        kijun_retest_bearish=False,
        kijun_bounce_bullish=False,
        kijun_bounce_bearish=False,
        kumo_orientation="BULLISH",
        kumo_twist=False,
        bars_since_kumo_twist=None,
        kumo_thickness_atr=None,
        kumo_thickness_pct=None,
    )
    base.update(overrides)
    return FeatureBar(**base)


def test_parse_ruleset_rejects_unknown_condition():
    with pytest.raises(ValueError, match="unknown condition"):
        parse_ruleset(
            {
                "id": "X",
                "direction": "LONG",
                "conditions": {"magic_sauce": True},
            }
        )


def test_parse_ruleset_ok():
    rs = parse_ruleset(
        {
            "id": "IV_TEST",
            "direction": "LONG",
            "conditions": {"rvol_min": 1.5, "price_above_kumo": True},
            "stop_atr": 1.0,
            "target_atr": 2.0,
        }
    )
    assert rs.id == "IV_TEST"
    assert rs.conditions["rvol_min"] == 1.5
    assert rs.condition_group.is_legacy_flat()


def test_builtin_catalog_nonempty():
    items = list_builtin_rulesets()
    assert len(items) >= 3
    assert get_builtin_ruleset("IV_ICHIMOKU_ONLY_LONG_001").id.startswith("IV_")


def test_rising_edge_signals():
    candles = []
    for i in range(80):
        base = 100 + i * 0.5
        vol = 500.0 if 50 <= i <= 55 else 100.0
        candles.append(_c(i, base, base + 1, base - 0.5, base + 0.8, vol))

    features = build_feature_series(candles)
    rs = parse_ruleset(
        {
            "id": "IV_RVOL_ONLY",
            "direction": "LONG",
            "conditions": {"rvol_min": 2.0},
        }
    )
    mask = matches_mask(features, rs)
    signals = extract_ruleset_signals(features, rs, rising_edge=True)
    assert sum(mask) >= len(signals)
    assert all(mask[i] for i, _ in signals)
    for i, _ in signals:
        if i > 0:
            assert not mask[i - 1]


def test_study_ruleset_on_candles_runs():
    candles = []
    for i in range(100):
        base = 100 + i * 0.3
        candles.append(_c(i, base, base + 2, base - 1, base + 1, 100 + (50 if i % 17 == 0 else 0)))

    rs = get_builtin_ruleset("IV_ICHIMOKU_ONLY_LONG_001")
    result = study_ruleset_on_candles(
        candles, rs, symbol="TEST", timeframe="1h", horizons=(1, 3, 5)
    )
    assert result.n_bars == 100
    assert result.event_study.variant == rs.id
    assert result.n_signals == result.event_study.n_events or result.n_signals >= result.event_study.n_events


def test_flat_equals_nested_all():
    flat = parse_ruleset(
        {
            "id": "EQ",
            "direction": "LONG",
            "conditions": {"rvol_min": 1.5, "price_above_kumo": True},
        }
    )
    nested = parse_ruleset(
        {
            "id": "EQ",
            "direction": "LONG",
            "conditions": {
                "all": {"rvol_min": 1.5, "price_above_kumo": True},
            },
        }
    )
    assert flat.condition_group.all_of == nested.condition_group.all_of
    assert flat.condition_group.any_of == nested.condition_group.any_of
    bar_ok = _bare_bar(rvol=2.0, price_above_kumo=True)
    bar_no = _bare_bar(rvol=1.0, price_above_kumo=True)
    assert bar_matches(bar_ok, flat) is True
    assert bar_matches(bar_ok, nested) is True
    assert bar_matches(bar_no, flat) is False
    assert bar_matches(bar_no, nested) is False
    assert nested.to_dict()["conditions"] == {
        "rvol_min": 1.5,
        "price_above_kumo": True,
    }


def test_any_or_composition():
    rs = parse_ruleset(
        {
            "id": "OR",
            "direction": "LONG",
            "conditions": {
                "any": {"bos_bullish": True, "tk_cross_bullish": True},
            },
        }
    )
    assert bar_matches(_bare_bar(bos_bullish=True), rs) is True
    assert bar_matches(_bare_bar(tk_cross_bullish=True), rs) is True
    assert bar_matches(_bare_bar(), rs) is False


def test_all_and_any_composition():
    rs = parse_ruleset(
        {
            "id": "BOTH",
            "direction": "LONG",
            "conditions": {
                "all": {"rvol_min": 1.5},
                "any": {"bos_bullish": True, "tk_cross_bullish": True},
            },
        }
    )
    assert bar_matches(_bare_bar(rvol=2.0, bos_bullish=True), rs) is True
    assert bar_matches(_bare_bar(rvol=2.0, tk_cross_bullish=True), rs) is True
    assert bar_matches(_bare_bar(rvol=2.0), rs) is False
    assert bar_matches(_bare_bar(rvol=1.0, bos_bullish=True), rs) is False


def test_reject_mix_flat_and_composition_keys():
    with pytest.raises(ValueError, match="cannot mix"):
        parse_ruleset(
            {
                "id": "BAD",
                "direction": "LONG",
                "conditions": {"all": {"rvol_min": 1.5}, "price_above_kumo": True},
            }
        )


def test_reject_empty_all_any():
    with pytest.raises(ValueError, match="at least one leaf"):
        parse_ruleset(
            {
                "id": "BAD",
                "direction": "LONG",
                "conditions": {"all": {}, "any": {}},
            }
        )


def test_rising_edge_applies_to_combined_any_mask():
    candles = []
    for i in range(80):
        base = 100 + i * 0.5
        vol = 500.0 if 50 <= i <= 55 else 100.0
        candles.append(_c(i, base, base + 1, base - 0.5, base + 0.8, vol))
    features = build_feature_series(candles)
    rs = parse_ruleset(
        {
            "id": "ANY_RVOL",
            "direction": "LONG",
            "conditions": {"any": {"rvol_min": 2.0}},
        }
    )
    mask = matches_mask(features, rs)
    signals = extract_ruleset_signals(features, rs, rising_edge=True)
    assert sum(mask) >= len(signals)
    for i, _ in signals:
        if i > 0:
            assert not mask[i - 1]


def test_catalog_builtins_still_parse_and_match_flat():
    for rs in list_builtin_rulesets():
        assert rs.condition_group.is_legacy_flat()
        assert rs.conditions
        again = parse_ruleset(rs.to_dict())
        assert again.condition_group.all_of == rs.condition_group.all_of
