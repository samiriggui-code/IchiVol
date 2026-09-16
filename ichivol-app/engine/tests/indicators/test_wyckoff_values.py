from __future__ import annotations

from app.indicators.donchian import DonchianParams, compute_donchian
from app.indicators.ichimoku import Candle
from app.indicators.wyckoff import WyckoffParams, WyckoffPhase, compute_wyckoff


def _flat_range(n: int, low: float = 95.0, high: float = 105.0, volume: float = 10.0) -> list[Candle]:
    # Alternates between touching the top and touching the bottom of
    # [low, high] -- establishes a clean, well-defined Donchian range.
    candles = []
    for i in range(n):
        if i % 2 == 0:
            candles.append(Candle(time=i, open=high - 1, high=high, low=high - 3, close=high - 1, volume=volume))
        else:
            candles.append(Candle(time=i, open=low + 1, high=low + 3, low=low, close=low + 1, volume=volume))
    return candles


def _wyckoff_after(extra: Candle, n_range: int = 25) -> WyckoffPhase:
    candles = _flat_range(n_range) + [extra]
    donchian = compute_donchian(candles, DonchianParams(period=20))
    states = compute_wyckoff(candles, donchian, WyckoffParams())
    return states[-1]


def test_reports_unknown_before_enough_history():
    candles = _flat_range(10)
    donchian = compute_donchian(candles, DonchianParams(period=20))
    states = compute_wyckoff(candles, donchian, WyckoffParams())
    assert all(s.phase == WyckoffPhase.UNKNOWN for s in states)


def test_a_reabsorbed_breakdown_on_climax_volume_is_a_spring():
    # Wicks below the established range low (95) but closes back above it,
    # on 3x the trailing average volume.
    spring_bar = Candle(time=25, open=90.0, high=99.0, low=85.0, close=98.0, volume=30.0)
    state = _wyckoff_after(spring_bar)
    assert state.phase == WyckoffPhase.SPRING
    assert state.tested_level == 95.0


def test_a_rejected_breakout_on_climax_volume_is_an_upthrust():
    upthrust_bar = Candle(time=25, open=110.0, high=115.0, low=101.0, close=102.0, volume=30.0)
    state = _wyckoff_after(upthrust_bar)
    assert state.phase == WyckoffPhase.UPTHRUST
    assert state.tested_level == 105.0


def test_a_reabsorbed_breakdown_without_volume_climax_is_not_a_spring():
    # Same wick-and-reclaim shape as the spring case, but ordinary volume --
    # the climax gate exists specifically to reject this.
    quiet_bar = Candle(time=25, open=90.0, high=99.0, low=85.0, close=98.0, volume=10.0)
    state = _wyckoff_after(quiet_bar)
    assert state.phase != WyckoffPhase.SPRING


def test_a_bar_fully_contained_in_the_range_is_ranging():
    contained_bar = Candle(time=25, open=100.0, high=101.0, low=99.0, close=100.0, volume=10.0)
    state = _wyckoff_after(contained_bar)
    assert state.phase == WyckoffPhase.RANGING
    assert state.tested_level is None


def test_a_clean_breakout_that_holds_is_trending_not_a_test():
    # Closes decisively above the range, no same-bar reclaim -- a real
    # breakout, not a false one.
    breakout_bar = Candle(time=25, open=106.0, high=110.0, low=106.0, close=108.0, volume=10.0)
    state = _wyckoff_after(breakout_bar)
    assert state.phase == WyckoffPhase.TRENDING
    assert state.tested_level is None
