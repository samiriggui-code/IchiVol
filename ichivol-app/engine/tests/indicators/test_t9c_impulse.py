"""T9c — causal impulse / displacement; anti-lookahead; threshold gate."""

from __future__ import annotations

from app.indicators.ichimoku import Candle
from app.indicators.impulse import ImpulseParams, compute_impulse
from app.indicators.structure import StructureParams, compute_structure
from tests.indicators.test_ichimoku_lookahead import _make_candles


def _candles(ohlc: list[tuple[float, float, float, float]]) -> list[Candle]:
    return [
        Candle(time=i, open=o, high=h, low=lo, close=c, volume=100.0)
        for i, (o, h, lo, c) in enumerate(ohlc)
    ]


def test_impulse_params_are_explicit_not_magic():
    p = ImpulseParams()
    assert isinstance(p.swing_lookback, int)
    assert isinstance(p.min_displacement_atr, float)
    assert p.min_rvol is None or isinstance(p.min_rvol, float)


def test_bullish_impulse_on_clear_low_to_high_leg():
    """Low pivot → high pivot with large range → bullish impulse at confirm."""
    ohlc: list[tuple[float, float, float, float]] = []
    for i in range(30):
        base = 100.0 + i * 0.1
        ohlc.append((base, base + 1.0, base - 1.0, base))
    # Deep low around bar 10, then spike high around bar 18–20.
    ohlc[10] = (100.0, 101.0, 50.0, 55.0)
    ohlc[11] = (55.0, 60.0, 54.0, 58.0)
    ohlc[12] = (58.0, 62.0, 56.0, 60.0)
    ohlc[18] = (60.0, 200.0, 59.0, 190.0)
    ohlc[19] = (190.0, 210.0, 180.0, 200.0)
    ohlc[20] = (200.0, 220.0, 195.0, 210.0)

    states = compute_impulse(
        _candles(ohlc), ImpulseParams(swing_lookback=2, min_displacement_atr=1.0)
    )
    bull = [s for s in states if s.event is not None and s.event.direction == "bullish"]
    assert bull, "expected at least one bullish impulse"
    ev = bull[-1].event
    assert ev is not None
    assert ev.start_price < ev.end_price
    assert ev.displacement_atr >= 1.0
    assert states[ev.bar].active is not None


def test_threshold_gates_small_legs():
    """Tiny range relative to ATR → no impulse; same series with tiny threshold fires."""
    candles = _make_candles(80, seed=11)
    none = compute_impulse(
        candles, ImpulseParams(swing_lookback=2, min_displacement_atr=1e9)
    )
    assert all(s.event is None for s in none)

    some = compute_impulse(
        candles, ImpulseParams(swing_lookback=2, min_displacement_atr=0.01)
    )
    assert any(s.event is not None for s in some)


def test_impulse_anti_lookahead():
    """An impulse known at bar b is absent on any prefix ending before b."""
    candles = _make_candles(100, seed=17)
    params = ImpulseParams(swing_lookback=2, min_displacement_atr=0.5)
    full = compute_impulse(candles, params)
    events = [s for s in full if s.event is not None]
    assert events, "need at least one impulse for anti-lookahead (lower threshold)"
    for s in events:
        b = s.event.bar
        trunc = compute_impulse(candles[:b], params)
        assert not any(
            t.event is not None
            and t.event.direction == s.event.direction
            and t.event.start_bar == s.event.start_bar
            and t.event.end_bar == s.event.end_bar
            for t in trunc
        )
        inclusive = compute_impulse(candles[: b + 1], params)
        assert any(
            t.event is not None
            and t.event.bar == b
            and t.event.direction == s.event.direction
            for t in inclusive
        )


def test_impulse_does_not_change_structure_bos():
    """Additive: structure bos/bias on same candles unchanged by impulse module."""
    candles = _make_candles(120, seed=23)
    struct = compute_structure(candles, StructureParams(swing_lookback=2))
    _ = compute_impulse(candles, ImpulseParams(swing_lookback=2))
    again = compute_structure(candles, StructureParams(swing_lookback=2))
    assert [s.bos for s in struct] == [s.bos for s in again]
    assert [s.bias for s in struct] == [s.bias for s in again]
