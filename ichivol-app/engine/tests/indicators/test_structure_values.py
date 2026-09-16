from __future__ import annotations

from app.indicators.ichimoku import Candle
from app.indicators.structure import BosEvent, StructureBias, StructureParams, compute_structure

PARAMS = StructureParams(swing_lookback=2)


def _candles(ohlc: list[tuple[float, float, float, float]]) -> list[Candle]:
    return [
        Candle(time=i, open=o, high=h, low=lo, close=c, volume=1.0)
        for i, (o, h, lo, c) in enumerate(ohlc)
    ]


def test_insufficient_history_is_unknown_not_a_crash():
    candles = _candles([(1, 1, 1, 1)] * 3)
    states = compute_structure(candles, PARAMS)
    assert len(states) == 3
    assert states[0].bias == StructureBias.UNKNOWN
    assert states[0].last_swing_high is None


def test_a_clean_uptrend_of_higher_highs_and_higher_lows_is_bullish():
    # A real zig-zag: peak, deeper trough, higher peak, higher (but still
    # higher-than-first-trough) trough. A monotonic run has no local
    # extrema at all -- swings only exist at genuine reversals.
    ohlc = [
        (100, 102, 98, 101),
        (101, 105, 101, 104),
        (104, 110, 104, 106),  # PEAK1 = 110
        (106, 106, 100, 102),
        (102, 103, 95, 97),  # TROUGH1 = 95
        (97, 108, 99, 107),
        (107, 120, 110, 118),  # PEAK2 = 120 (higher high)
        (118, 119, 105, 108),
        (108, 112, 100, 105),  # TROUGH2 = 100 (higher low than 95)
        (105, 116, 105, 114),
        (114, 118, 108, 117),  # confirms TROUGH2 -> HH + HL now both known
    ]
    candles = _candles(ohlc)
    states = compute_structure(candles, PARAMS)
    assert states[-1].bias == StructureBias.BULLISH
    assert states[-1].last_swing_high == 120
    assert states[-1].last_swing_low == 100


def test_bos_fires_when_close_breaks_the_last_confirmed_swing_high():
    # Build a small range, then a clean breakout candle.
    ohlc = [
        (100, 102, 98, 100),
        (100, 101, 97, 99),
        (99, 103, 98, 100),  # local high ~103
        (100, 101, 96, 97),
        (97, 99, 95, 96),  # local low ~95
        (96, 100, 95, 99),
        (99, 100, 96, 100),
        (100, 115, 99, 114),  # breakout well above the local high
    ]
    candles = _candles(ohlc)
    states = compute_structure(candles, PARAMS)
    assert any(s.bos == BosEvent.BULLISH for s in states)
