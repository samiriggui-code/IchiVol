from __future__ import annotations

from app.indicators.adx import AdxParams, TrendStrength, compute_adx
from app.indicators.ichimoku import Candle


def _candle(time: int, high: float, low: float, close: float) -> Candle:
    return Candle(time=time, open=close, high=high, low=low, close=close, volume=10.0)


def _steady_uptrend(n: int, step: float = 2.0) -> list[Candle]:
    # A clean, sustained uptrend -- classic textbook "ADX should rise and
    # cross the trending threshold" scenario.
    candles = []
    price = 100.0
    for i in range(n):
        price += step
        candles.append(_candle(i, high=price + 1.0, low=price - 0.5, close=price))
    return candles


def _choppy_sideways(n: int) -> list[Candle]:
    # Oscillates around a fixed level with no net direction -- +DM and -DM
    # roughly cancel out bar to bar, the classic low-ADX chop case.
    candles = []
    for i in range(n):
        wiggle = 2.0 if i % 2 == 0 else -2.0
        price = 100.0 + wiggle
        candles.append(_candle(i, high=price + 1.0, low=price - 1.0, close=price))
    return candles


def test_reports_unknown_before_enough_history():
    candles = _steady_uptrend(10)
    states = compute_adx(candles, AdxParams(period=14))
    assert all(s.adx is None and s.strength == TrendStrength.UNKNOWN for s in states)


def test_sustained_trend_is_eventually_classified_trending_or_strong():
    candles = _steady_uptrend(80)
    states = compute_adx(candles, AdxParams(period=14))
    last = states[-1]
    assert last.adx is not None
    assert last.strength in (TrendStrength.TRENDING, TrendStrength.STRONG)
    assert last.plus_di > last.minus_di  # uptrend -> +DI dominates


def test_uptrend_has_higher_plus_di_than_minus_di():
    candles = _steady_uptrend(60)
    states = compute_adx(candles, AdxParams(period=14))
    last = states[-1]
    assert last.plus_di is not None and last.minus_di is not None
    assert last.plus_di > last.minus_di


def test_choppy_sideways_market_is_not_classified_as_a_strong_trend():
    candles = _choppy_sideways(80)
    states = compute_adx(candles, AdxParams(period=14))
    last = states[-1]
    assert last.strength in (TrendStrength.ABSENT, TrendStrength.DEVELOPING)


def test_adx_stays_within_0_and_100():
    candles = _steady_uptrend(100)
    states = compute_adx(candles, AdxParams(period=14))
    for s in states:
        if s.adx is not None:
            assert 0.0 <= s.adx <= 100.0
