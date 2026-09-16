from __future__ import annotations

import pytest

from app.indicators.atr import AtrParams, VolatilityRegime, compute_atr
from app.indicators.ichimoku import Candle


def _flat_candles(n: int, price: float = 100.0) -> list[Candle]:
    return [
        Candle(time=i, open=price, high=price, low=price, close=price, volume=1.0)
        for i in range(n)
    ]


def test_flat_candles_have_zero_true_range_and_atr():
    states = compute_atr(_flat_candles(30))
    last = states[-1]
    assert last.true_range == 0.0
    assert last.atr == 0.0


def test_true_range_accounts_for_a_gap_beyond_the_bars_own_range():
    candles = [
        Candle(time=0, open=100, high=101, low=99, close=100, volume=1.0),
        # small intrabar range (110-108=2) but a big gap up from prev close (100 -> 108)
        Candle(time=1, open=108, high=110, low=108, close=109, volume=1.0),
    ]
    states = compute_atr(candles)
    assert states[1].true_range == pytest.approx(10.0)  # |110 - 100|


def test_single_bar_has_unknown_regime_not_a_crash():
    states = compute_atr(_flat_candles(1))
    assert len(states) == 1
    assert states[0].regime == VolatilityRegime.UNKNOWN
    assert states[0].percentile is None


def test_a_volatility_spike_after_a_calm_period_is_classified_extreme():
    calm = _flat_candles(150, price=100.0)
    spike = [
        Candle(time=150 + i, open=100, high=100 + 50 * (i + 1), low=100, close=100, volume=1.0)
        for i in range(3)
    ]
    states = compute_atr(calm + spike, AtrParams(period=1))
    assert states[-1].regime == VolatilityRegime.EXTREME


def test_a_calm_period_after_high_volatility_is_classified_dead():
    volatile = [
        Candle(time=i, open=100, high=100 + 20 * ((i % 5) + 1), low=100, close=100, volume=1.0)
        for i in range(150)
    ]
    calm = _flat_candles(5, price=100.0)
    states = compute_atr(volatile + calm, AtrParams(period=1))
    assert states[-1].regime == VolatilityRegime.DEAD


def test_suggested_stop_distance_scales_with_atr():
    states = compute_atr(_flat_candles(30, price=100.0), AtrParams(stop_multiplier=2.0))
    assert states[-1].suggested_stop_distance == 0.0  # zero ATR -> zero stop hint, not None
