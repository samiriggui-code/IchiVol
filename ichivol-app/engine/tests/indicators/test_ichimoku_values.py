from __future__ import annotations

from app.indicators.ichimoku import (
    Candle,
    ChikouState,
    CrossState,
    IchimokuParams,
    PriceVsKumo,
    compute_ichimoku,
)


def _flat_candles(n: int, price: float = 100.0) -> list[Candle]:
    return [
        Candle(time=i, open=price, high=price, low=price, close=price, volume=1.0)
        for i in range(n)
    ]


def test_insufficient_history_yields_unknown_not_a_crash():
    params = IchimokuParams(tenkan=9, kijun=26, senkou_b=52, displacement=26)
    candles = _flat_candles(5)
    states = compute_ichimoku(candles, params)
    assert len(states) == 5
    assert states[0].tenkan is None
    assert states[0].price_vs_kumo == PriceVsKumo.UNKNOWN
    assert states[0].chikou_state == ChikouState.UNKNOWN


def test_flat_market_has_zero_thickness_and_no_cross():
    params = IchimokuParams(tenkan=9, kijun=26, senkou_b=52, displacement=26)
    candles = _flat_candles(120, price=50.0)
    states = compute_ichimoku(candles, params)
    last = states[-1]
    assert last.tenkan == 50.0
    assert last.kijun == 50.0
    assert last.cloud_top == last.cloud_bot == 50.0
    assert last.kumo_thickness == 0.0
    assert last.tk_cross == CrossState.NONE
    assert last.price_vs_kumo == PriceVsKumo.INSIDE


def test_tenkan_is_donchian_midpoint_of_its_window():
    params = IchimokuParams(tenkan=3, kijun=5, senkou_b=8, displacement=2)
    highs_lows = [
        (10, 8),
        (11, 9),
        (9, 7),
        (12, 10),
        (13, 11),
    ]
    candles = [
        Candle(time=i, open=lo, high=hi, low=lo, close=(hi + lo) / 2, volume=1.0)
        for i, (hi, lo) in enumerate(highs_lows)
    ]
    states = compute_ichimoku(candles, params)
    # tenkan(3) at i=2 uses bars 0..2: high=max(10,11,9)=11, low=min(8,9,7)=7 -> 9.0
    assert states[2].tenkan == 9.0
    # tenkan(3) at i=4 uses bars 2..4: high=max(9,12,13)=13, low=min(7,10,11)=7 -> 10.0
    assert states[4].tenkan == 10.0


def test_sustained_uptrend_is_classified_bullish_with_high_score():
    params = IchimokuParams(tenkan=9, kijun=26, senkou_b=52, displacement=26)
    n = 160
    candles = [
        Candle(time=i, open=100 + i, high=101 + i, low=99 + i, close=100.5 + i, volume=1.0)
        for i in range(n)
    ]
    last = compute_ichimoku(candles, params)[-1]
    assert last.price_vs_kumo == PriceVsKumo.ABOVE
    assert last.future_kumo == CrossState.BULLISH
    assert last.chikou_state == ChikouState.CLEAR_BULLISH
    assert last.score is not None and last.score > 0
