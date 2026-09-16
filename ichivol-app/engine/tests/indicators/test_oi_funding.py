from __future__ import annotations

from app.indicators.ichimoku import Candle
from app.indicators.oi_funding import (
    FundingBias,
    OiFundingParams,
    OiTrend,
    compute_oi_funding,
)
from app.market_data.binance_futures import FundingPoint, OpenInterestPoint


def _candle(time: int) -> Candle:
    return Candle(time=time, open=100, high=101, low=99, close=100.5, volume=10.0)


def test_rising_open_interest_is_classified_rising():
    candles = [_candle(i * 3600) for i in range(25)]
    oi_points = [OpenInterestPoint(time=i * 3600, open_interest=1000.0 * (1 + i * 0.01)) for i in range(25)]
    states = compute_oi_funding(candles, oi_points, [], OiFundingParams(oi_window=20))
    assert states[-1].oi_trend == OiTrend.RISING


def test_falling_open_interest_is_classified_falling():
    candles = [_candle(i * 3600) for i in range(25)]
    oi_points = [OpenInterestPoint(time=i * 3600, open_interest=1000.0 * (1 - i * 0.01)) for i in range(25)]
    states = compute_oi_funding(candles, oi_points, [], OiFundingParams(oi_window=20))
    assert states[-1].oi_trend == OiTrend.FALLING


def test_stable_open_interest_is_classified_flat():
    candles = [_candle(i * 3600) for i in range(25)]
    oi_points = [OpenInterestPoint(time=i * 3600, open_interest=1000.0) for i in range(25)]
    states = compute_oi_funding(candles, oi_points, [], OiFundingParams(oi_window=20))
    assert states[-1].oi_trend == OiTrend.FLAT


def test_no_open_interest_data_reports_unknown_not_a_crash():
    candles = [_candle(0)]
    states = compute_oi_funding(candles, [], [])
    assert states[0].oi_trend == OiTrend.UNKNOWN
    assert states[0].open_interest is None


def test_high_positive_funding_is_crowded_long():
    candles = [_candle(0)]
    funding = [FundingPoint(time=0, rate=0.001)]
    states = compute_oi_funding(candles, [], funding)
    assert states[0].funding_bias == FundingBias.CROWDED_LONG


def test_high_negative_funding_is_crowded_short():
    candles = [_candle(0)]
    funding = [FundingPoint(time=0, rate=-0.001)]
    states = compute_oi_funding(candles, [], funding)
    assert states[0].funding_bias == FundingBias.CROWDED_SHORT


def test_small_funding_is_neutral():
    candles = [_candle(0)]
    funding = [FundingPoint(time=0, rate=0.00001)]
    states = compute_oi_funding(candles, [], funding)
    assert states[0].funding_bias == FundingBias.NEUTRAL


def test_funding_before_any_known_point_is_unknown():
    candles = [_candle(0), _candle(3600)]
    funding = [FundingPoint(time=7200, rate=0.001)]  # only known in the future relative to both candles
    states = compute_oi_funding(candles, [], funding)
    assert all(s.funding_bias == FundingBias.UNKNOWN for s in states)


def test_funding_holds_the_last_known_rate_between_8h_resets():
    # Funding events are sparse (~8h apart) relative to hourly candles --
    # the rate in effect must carry forward, not reset to UNKNOWN between events.
    candles = [_candle(i * 3600) for i in range(10)]
    funding = [FundingPoint(time=0, rate=0.001), FundingPoint(time=5 * 3600, rate=-0.001)]
    states = compute_oi_funding(candles, [], funding)
    for i in range(5):
        assert states[i].funding_rate == 0.001
    for i in range(5, 10):
        assert states[i].funding_rate == -0.001
