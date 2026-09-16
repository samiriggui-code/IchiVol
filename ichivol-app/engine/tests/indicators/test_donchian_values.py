from __future__ import annotations

from app.indicators.donchian import DonchianBreakout, DonchianParams, compute_donchian
from app.indicators.ichimoku import Candle


def _flat_range(n: int, low: float = 95.0, high: float = 105.0) -> list[Candle]:
    # Oscillates inside [low, high] forever -- never breaks its own range.
    candles = []
    for i in range(n):
        mid = low + 5.0 if i % 2 == 0 else high - 5.0
        candles.append(Candle(time=i, open=mid, high=mid + 2.0, low=mid - 2.0, close=mid, volume=10.0))
    return candles


def test_reports_unknown_before_enough_history():
    candles = _flat_range(10)
    states = compute_donchian(candles, DonchianParams(period=20))
    assert all(s.breakout == DonchianBreakout.UNKNOWN and s.upper is None for s in states)


def test_range_bound_series_never_reports_a_breakout_once_established():
    candles = _flat_range(60, low=95.0, high=105.0)
    states = compute_donchian(candles, DonchianParams(period=20))
    for s in states[20:]:
        assert s.breakout == DonchianBreakout.INSIDE


def test_a_clean_close_above_the_prior_range_is_an_up_breakout():
    candles = _flat_range(30, low=95.0, high=105.0)
    # One decisive bar closing well above anything seen in the prior window.
    candles.append(Candle(time=30, open=106.0, high=120.0, low=106.0, close=118.0, volume=10.0))
    states = compute_donchian(candles, DonchianParams(period=20))
    assert states[-1].breakout == DonchianBreakout.UP
    assert states[-1].upper is not None and states[-1].upper < 108.0  # built from the flat range, not the spike itself


def test_a_clean_close_below_the_prior_range_is_a_down_breakout():
    candles = _flat_range(30, low=95.0, high=105.0)
    candles.append(Candle(time=30, open=94.0, high=94.0, low=80.0, close=82.0, volume=10.0))
    states = compute_donchian(candles, DonchianParams(period=20))
    assert states[-1].breakout == DonchianBreakout.DOWN


def test_the_breakout_bar_itself_is_excluded_from_its_own_band():
    # A single explosive bar should never "contain itself" -- the band
    # judging it must come only from bars strictly before it.
    candles = _flat_range(25, low=95.0, high=105.0)
    candles.append(Candle(time=25, open=105.0, high=200.0, low=105.0, close=200.0, volume=10.0))
    states = compute_donchian(candles, DonchianParams(period=20))
    assert states[-1].upper is not None and states[-1].upper < 110.0
    assert states[-1].breakout == DonchianBreakout.UP
