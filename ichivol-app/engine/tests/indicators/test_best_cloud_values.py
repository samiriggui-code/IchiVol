"""BEST Cloud value tests."""

from __future__ import annotations

import pytest

from app.indicators.best_cloud import (
    BestCloudParams,
    CloudCross,
    CloudTrend,
    compute_best_cloud,
)
from app.indicators.ichimoku import Candle

P = BestCloudParams(fast_period=5, slow_period=10)


def _series(closes: list[float]) -> list[Candle]:
    return [
        Candle(time=i, open=c, high=c + 1, low=c - 1, close=c, volume=1.0)
        for i, c in enumerate(closes)
    ]


def test_sma_values_and_warmup():
    closes = [float(i) for i in range(1, 31)]
    p = BestCloudParams(fast_period=3, slow_period=6, fast_type="SMA", slow_type="SMA")
    st = compute_best_cloud(_series(closes), p)
    assert st[1].fast_ma is None and st[2].fast_ma == pytest.approx(2.0)
    assert st[4].slow_ma is None and st[5].slow_ma == pytest.approx(3.5)
    assert st[-1].fast_ma == pytest.approx(29.0)
    assert st[-1].slow_ma == pytest.approx(27.5)
    assert st[3].trend == CloudTrend.UNKNOWN
    assert st[-1].cloud_upper == pytest.approx(29.0)
    assert st[-1].cloud_lower == pytest.approx(27.5)
    assert st[-1].cloud_width == pytest.approx(1.5)


def test_uptrend_is_bullish_above_cloud():
    st = compute_best_cloud(_series([100 + i for i in range(60)]), P)[-1]
    assert st.trend == CloudTrend.BULLISH
    assert st.price_above_cloud and not st.price_below_cloud and not st.price_inside_cloud
    assert st.distance_price_cloud_pct > 0


def test_downtrend_is_bearish_below_cloud():
    st = compute_best_cloud(_series([200 - i for i in range(60)]), P)[-1]
    assert st.trend == CloudTrend.BEARISH
    assert st.price_below_cloud
    assert st.distance_price_cloud_pct < 0


def test_price_inside_cloud_is_neutral():
    closes = [100 + i for i in range(50)]
    before = compute_best_cloud(_series(closes), P)[-1]
    closes.append((before.fast_ma + before.slow_ma) / 2)
    st = compute_best_cloud(_series(closes), P)[-1]
    assert st.price_inside_cloud
    assert st.trend == CloudTrend.NEUTRAL
    assert st.distance_price_cloud_pct == 0.0


def test_cross_detection_and_age():
    closes = [100 - i * 0.5 for i in range(40)] + [80 + i for i in range(40)]
    st = compute_best_cloud(_series(closes), P)
    idx = [i for i, s in enumerate(st) if s.cross == CloudCross.BULLISH_CROSS]
    assert idx
    i = idx[0]
    assert st[i].bars_since_cross == 0
    assert st[i + 4].bars_since_cross == 4
    assert st[i].last_cross == CloudCross.BULLISH_CROSS
    assert st[i].fast_ma > st[i].slow_ma and st[i - 1].fast_ma <= st[i - 1].slow_ma


def test_constant_price_no_cross_no_trend():
    st = compute_best_cloud(_series([50.0] * 40), P)[-1]
    assert st.cross == CloudCross.NONE and st.bars_since_cross is None
    assert st.trend == CloudTrend.NEUTRAL


def test_params_validation():
    with pytest.raises(ValueError):
        BestCloudParams(fast_period=50, slow_period=20)
    with pytest.raises(ValueError):
        BestCloudParams(fast_type="HMA")
