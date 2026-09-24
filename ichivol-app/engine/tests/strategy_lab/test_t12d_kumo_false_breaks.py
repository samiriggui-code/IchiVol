"""T12d — kumo breakout continuation vs failure at explicit N."""

from __future__ import annotations

import pytest

from types import SimpleNamespace

from app.indicators.ichimoku import Candle
from app.strategy_lab.features import FeatureBar
from app.strategy_lab.kumo_false_breaks import (
    DEFAULT_HORIZON_N,
    study_kumo_false_breaks_on_candles,
    study_kumo_false_breaks_on_features,
)
from tests.indicators.test_ichimoku_lookahead import _make_candles


def _bar(**kwargs) -> FeatureBar:
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
        kijun_slope_state="UNKNOWN",
        kijun_slope_atr_normalized=None,
        price_kijun_distance_atr=None,
        kijun_break_bullish=False,
        kijun_break_bearish=False,
        kijun_retest_bullish=False,
        kijun_retest_bearish=False,
        kijun_bounce_bullish=False,
        kijun_bounce_bearish=False,
        kumo_orientation="UNKNOWN",
        kumo_twist=False,
        bars_since_kumo_twist=None,
        kumo_thickness_atr=None,
        kumo_thickness_pct=None,
    )
    base.update(kwargs)
    return FeatureBar(**base)


def test_horizon_n_must_be_positive():
    with pytest.raises(ValueError, match="horizon_n"):
        study_kumo_false_breaks_on_candles(_make_candles(80), horizon_n=0)


def test_bullish_continuation_and_failure_at_n():
    """Sonde : cassure haussière + prix toujours au-dessus → continuation ; sous → failure."""
    # Build a minimal FeatureSeries-like via study on synthetic with controlled bars
    # Use real candles then override via direct feature study on a handcrafted series.
    n = 20
    bars = []
    for i in range(n):
        bars.append(
            _bar(
                index=i,
                time=i * 3600,
                kumo_breakout_bullish=(i == 5),
                price_above_kumo=(i >= 5 and i != 5 + DEFAULT_HORIZON_N),
                price_below_kumo=(i == 5 + DEFAULT_HORIZON_N),
                rvol_eleve=True,
                regime_trending=True,
                structure_bias_bullish=True,
                above_vwap=True,
                cvd_bias="BUY",
            )
        )
    # At i=5 breakout; at i=10 (=5+5) we set below → failure
    # Second breakout at i=12 continuing above at i=17
    bars[12] = _bar(
        index=12,
        time=12 * 3600,
        kumo_breakout_bullish=True,
        price_above_kumo=True,
        rvol_fort=True,
        regime_ranging=True,
        structure_bias_bearish=True,
        below_vwap=True,
        cvd_bias="SELL",
    )
    for i in range(13, n):
        bars[i] = _bar(
            index=i,
            time=i * 3600,
            price_above_kumo=True,
            rvol_normal=True,
        )

    # Fake FeatureSeries: only bars needed by the study
    report = study_kumo_false_breaks_on_features(
        SimpleNamespace(bars=bars),  # type: ignore[arg-type]
        horizon_n=DEFAULT_HORIZON_N,
        symbol="TEST",
        timeframe="1h",
    )
    assert report.horizon_n == 5
    assert report.n_events == 2
    by_idx = {e.index: e for e in report.events}
    assert by_idx[5].outcome == "failure"
    assert by_idx[5].side == "bullish"
    assert by_idx[5].context["rvol_band"] == "eleve"
    assert by_idx[5].context["adx_regime"] == "trending"
    assert by_idx[5].context["structure"] == "bull"
    assert by_idx[5].context["cvd"] == "buy"
    assert by_idx[12].outcome == "continuation"
    assert by_idx[12].context["rvol_band"] == "fort"
    assert "rvol_band" in report.slices
    assert report.slices["rvol_band"]["eleve"]["failure"] == 1
    assert report.slices["rvol_band"]["fort"]["continuation"] == 1


def test_incomplete_when_series_too_short():
    bars = [
        _bar(index=0, time=0),
        _bar(index=1, time=3600, kumo_breakout_bullish=True, price_above_kumo=True),
        _bar(index=2, time=7200, price_above_kumo=True),
    ]

    report = study_kumo_false_breaks_on_features(
        SimpleNamespace(bars=bars), horizon_n=5  # type: ignore[arg-type]
    )
    assert report.n_events == 1
    assert report.events[0].outcome == "incomplete"
    assert report.n_incomplete == 1


def test_empty_and_one_bar_ok():
    report0 = study_kumo_false_breaks_on_candles([], horizon_n=3)
    assert report0.n_events == 0
    one = [Candle(time=0, open=1, high=1, low=1, close=1, volume=1)]
    report1 = study_kumo_false_breaks_on_candles(one, horizon_n=3)
    assert report1.n_bars == 1
    assert report1.n_events == 0


def test_real_series_runs_and_slices_present():
    candles = _make_candles(260, seed=11)
    report = study_kumo_false_breaks_on_candles(
        candles, horizon_n=8, symbol="BTC", timeframe="1h"
    )
    assert report.horizon_n == 8
    assert report.n_bars == len(candles)
    assert report.n_events == report.n_continuation + report.n_failure + report.n_inside + report.n_incomplete
    for dim in ("rvol_band", "adx_regime", "structure", "location", "cvd"):
        assert dim in report.slices
    # Causality smoke: outcome_index is index + N when complete
    for ev in report.events:
        if ev.outcome != "incomplete":
            assert ev.outcome_index == ev.index + 8


def test_bearish_continuation_mirror():
    bars = [_bar(index=i, time=i) for i in range(12)]
    bars[2] = _bar(
        index=2,
        time=2,
        kumo_breakout_bearish=True,
        price_below_kumo=True,
        rvol_faible=True,
        cvd_bias="SELL",
    )
    # N=3 → index 5 still below
    bars[5] = _bar(index=5, time=5, price_below_kumo=True)

    report = study_kumo_false_breaks_on_features(
        SimpleNamespace(bars=bars), horizon_n=3  # type: ignore[arg-type]
    )
    assert report.n_events == 1
    assert report.events[0].side == "bearish"
    assert report.events[0].outcome == "continuation"
