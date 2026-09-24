"""T10c — feature×feature redundancy (observation-only, no auto-reject)."""

from __future__ import annotations

import pytest

from app.agents.types import Direction
from app.strategy_lab.conditions import CONDITION_REGISTRY
from app.strategy_lab.features import FeatureBar, build_feature_series
from app.strategy_lab.redundancy import (
    boolean_condition_keys,
    feature_boolean_series,
    pairwise_overlap,
    run_feature_redundancy_study,
)
from tests.indicators.test_ichimoku_lookahead import _make_candles


def _minimal_bar(**overrides) -> FeatureBar:
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
        rvol=None,
        bos_bullish=False,
        bos_bearish=False,
        structure_bias_bullish=False,
        structure_bias_bearish=False,
        atr=None,
        atr_percentile=None,
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


def test_boolean_condition_keys_are_bool_registry_subset():
    keys = boolean_condition_keys()
    assert keys
    assert all(CONDITION_REGISTRY[k].value_type is bool for k in keys)
    assert set(keys) <= set(CONDITION_REGISTRY)


def test_pairwise_identical_and_complementary():
    a = [True, True, False, False, True]
    identical = pairwise_overlap(a, list(a))
    assert identical["jaccard"] == 1.0
    assert identical["phi"] == pytest.approx(1.0)

    b = [not x for x in a]
    comp = pairwise_overlap(a, b)
    assert comp["jaccard"] == 0.0
    assert comp["n_both"] == 0
    assert comp["phi"] == pytest.approx(-1.0)


def test_feature_boolean_series_direction_sensitive():
    bars = [
        _minimal_bar(kijun_retest_bullish=True, kijun_retest_bearish=False),
        _minimal_bar(index=1, time=1, kijun_retest_bullish=False, kijun_retest_bearish=True),
    ]
    long_hits = feature_boolean_series(bars, "kijun_retest", direction=Direction.LONG)
    short_hits = feature_boolean_series(bars, "kijun_retest", direction=Direction.SHORT)
    assert long_hits == [True, False]
    assert short_hits == [False, True]


def test_unknown_key_raises():
    with pytest.raises(ValueError, match="unknown"):
        feature_boolean_series([_minimal_bar()], "not_a_real_key", direction=Direction.LONG)


def test_run_feature_redundancy_study_shape_and_disclaimer():
    candles = _make_candles(120, seed=7)
    report = run_feature_redundancy_study(
        candles,
        symbol="BTCUSDT",
        timeframe="1h",
        direction=Direction.LONG,
        keys=["bos_bullish", "tk_cross_bullish", "price_above_kumo", "fvg_bullish"],
        min_true=1,
        top_n=5,
    )
    assert report.n_bars == 120
    assert report.symbol == "BTCUSDT"
    assert "no auto-reject" in report.disclaimer.lower()
    assert "alter decision" in report.disclaimer.lower()
    assert len(report.features) == 4
    by_key = {f.key: f for f in report.features}
    assert by_key["bos_bullish"].status == "PRODUCTION"
    assert by_key["bos_bullish"].family == "structure"
    # fvg_* conditions declare indicator_id="structure" (Lab leaf under structure family)
    assert by_key["fvg_bullish"].indicator_id == "structure"
    assert by_key["fvg_bullish"].status == "PRODUCTION"
    body = report.to_dict()
    assert "pairs" in body and "top_redundant" in body
    assert body["disclaimer"] == report.disclaimer


def test_study_skips_sparse_pairs():
    candles = _make_candles(80, seed=3)
    report = run_feature_redundancy_study(
        candles,
        symbol="ETHUSDT",
        timeframe="1h",
        keys=["bos_bullish", "choch_bullish"],
        min_true=10_000,  # force skip
        top_n=10,
    )
    assert report.pairs == []
    assert report.skipped_pairs == 1


def test_build_feature_series_compatible():
    series = build_feature_series(_make_candles(50, seed=1))
    hits = feature_boolean_series(
        series.bars, "price_above_kumo", direction=Direction.LONG
    )
    assert len(hits) == len(series.bars)
