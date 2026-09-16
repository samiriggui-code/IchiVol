from __future__ import annotations

from app.indicators.cvd import CvdBias, CvdParams, compute_cvd
from app.indicators.ichimoku import Candle


def _candle(time: int, volume: float, taker_buy_volume: float | None) -> Candle:
    return Candle(
        time=time, open=100, high=101, low=99, close=100.5,
        volume=volume, taker_buy_volume=taker_buy_volume,
    )


def test_delta_is_positive_when_buyers_dominate():
    candles = [_candle(0, volume=100.0, taker_buy_volume=80.0)]
    states = compute_cvd(candles)
    assert states[0].delta == 60.0  # 2*80 - 100


def test_delta_is_negative_when_sellers_dominate():
    candles = [_candle(0, volume=100.0, taker_buy_volume=20.0)]
    states = compute_cvd(candles)
    assert states[0].delta == -60.0  # 2*20 - 100


def test_cumulative_accumulates_across_bars():
    candles = [
        _candle(0, volume=100.0, taker_buy_volume=60.0),  # delta = 20
        _candle(1, volume=100.0, taker_buy_volume=70.0),  # delta = 40
    ]
    states = compute_cvd(candles)
    assert states[0].cumulative == 20.0
    assert states[1].cumulative == 60.0


def test_sustained_buy_pressure_is_classified_bullish():
    candles = [_candle(i, volume=100.0, taker_buy_volume=80.0) for i in range(25)]
    states = compute_cvd(candles, CvdParams(window=20, bias_threshold=0.1))
    assert states[-1].bias == CvdBias.BULLISH


def test_sustained_sell_pressure_is_classified_bearish():
    candles = [_candle(i, volume=100.0, taker_buy_volume=20.0) for i in range(25)]
    states = compute_cvd(candles, CvdParams(window=20, bias_threshold=0.1))
    assert states[-1].bias == CvdBias.BEARISH


def test_balanced_flow_is_classified_neutral():
    candles = [_candle(i, volume=100.0, taker_buy_volume=50.0) for i in range(25)]
    states = compute_cvd(candles, CvdParams(window=20, bias_threshold=0.1))
    assert states[-1].bias == CvdBias.NEUTRAL


def test_missing_taker_buy_volume_reports_unknown_gracefully():
    candles = [_candle(0, volume=100.0, taker_buy_volume=None)]
    states = compute_cvd(candles)
    assert states[0].bias == CvdBias.UNKNOWN
    assert states[0].delta is None
    assert states[0].cumulative is None


def test_zero_volume_bar_does_not_crash_the_rolling_ratio():
    candles = [_candle(0, volume=0.0, taker_buy_volume=0.0)]
    states = compute_cvd(candles)
    assert states[0].bias == CvdBias.UNKNOWN  # window_volume <= 0 -> can't form a ratio
