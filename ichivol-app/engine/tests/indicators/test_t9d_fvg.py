"""T9d — causal FVG; fill/invalidation; anti-lookahead; non-interference."""

from __future__ import annotations

from app.chart_objects.from_fvg import fvg_to_chart_objects
from app.chart_objects.types import ChartObjectLayer, ChartObjectType
from app.indicators.fvg import FvgParams, compute_fvg
from app.indicators.ichimoku import Candle
from app.indicators.impulse import ImpulseParams, compute_impulse
from app.indicators.structure import StructureParams, compute_structure
from tests.indicators.test_ichimoku_lookahead import _make_candles


def _candles(ohlc: list[tuple[float, float, float, float]]) -> list[Candle]:
    return [
        Candle(time=i * 60, open=o, high=h, low=lo, close=c, volume=100.0)
        for i, (o, h, lo, c) in enumerate(ohlc)
    ]


def test_fvg_params_explicit():
    p = FvgParams()
    assert isinstance(p.min_gap_atr, float)
    assert p.fill_mode in ("wick", "close")


def test_bullish_fvg_three_candle():
    # c0 high=100, c2 low=110 → gap [100, 110]
    ohlc = [
        (99, 100, 98, 99),
        (99, 108, 99, 107),  # displacement mid
        (107, 112, 110, 111),
    ]
    states = compute_fvg(_candles(ohlc), FvgParams(min_gap_atr=0.0))
    assert states[2].event is not None
    ev = states[2].event
    assert ev.direction == "bullish"
    assert ev.price_low == 100
    assert ev.price_high == 110
    assert ev.status == "open"
    assert len(states[2].active) == 1


def test_bearish_fvg_three_candle():
    ohlc = [
        (101, 102, 100, 101),
        (101, 101, 92, 93),
        (93, 94, 88, 90),  # c0.low=100 > c2.high=94
    ]
    states = compute_fvg(_candles(ohlc))
    assert states[2].event is not None
    assert states[2].event.direction == "bearish"


def test_no_fvg_when_ranges_overlap():
    ohlc = [
        (100, 105, 99, 104),
        (104, 106, 103, 105),
        (105, 107, 104, 106),  # overlap with c0
    ]
    states = compute_fvg(_candles(ohlc))
    assert states[2].event is None


def test_min_gap_atr_gate():
    ohlc = [
        (99, 100, 98, 99),
        (99, 108, 99, 107),
        (107, 112, 110, 111),
    ]
    none = compute_fvg(_candles(ohlc), FvgParams(min_gap_atr=1e9))
    assert none[2].event is None
    some = compute_fvg(_candles(ohlc), FvgParams(min_gap_atr=0.0))
    assert some[2].event is not None


def test_fvg_anti_lookahead():
    candles = _make_candles(120, seed=19)
    params = FvgParams(min_gap_atr=0.0)
    full = compute_fvg(candles, params)
    events = [s for s in full if s.event is not None]
    assert events, "need at least one FVG on random seed"
    for s in events:
        b = s.event.bar
        trunc = compute_fvg(candles[:b], params)
        assert not any(
            t.event is not None
            and t.event.direction == s.event.direction
            and t.event.price_low == s.event.price_low
            and t.event.price_high == s.event.price_high
            for t in trunc
        )
        inclusive = compute_fvg(candles[: b + 1], params)
        assert any(
            t.event is not None and t.event.bar == b for t in inclusive
        )


def test_fill_partial_then_filled():
    # Discover bullish FVG then wick into / through gap.
    ohlc = [
        (99, 100, 98, 99),
        (99, 108, 99, 107),
        (107, 112, 110, 111),  # discovery
        (111, 113, 105, 106),  # partial into gap
        (106, 107, 99, 100),   # fill through floor
    ]
    states = compute_fvg(_candles(ohlc))
    assert states[2].event is not None
    assert states[2].event.direction == "bullish"
    bull_key = (states[2].event.price_low, states[2].event.price_high)
    assert any(
        a.price_low == bull_key[0] and a.status == "partial" for a in states[3].active
    )
    # Original bullish gap no longer active after full fill
    assert not any(
        a.price_low == bull_key[0] and a.price_high == bull_key[1]
        for a in states[4].active
    )


def test_fvg_does_not_change_structure_or_impulse():
    candles = _make_candles(100, seed=23)
    s1 = compute_structure(candles, StructureParams())
    i1 = compute_impulse(candles, ImpulseParams())
    _ = compute_fvg(candles, FvgParams())
    s2 = compute_structure(candles, StructureParams())
    i2 = compute_impulse(candles, ImpulseParams())
    assert [x.bos for x in s1] == [x.bos for x in s2]
    assert [(x.event.bar if x.event else None) for x in i1] == [
        (x.event.bar if x.event else None) for x in i2
    ]


def test_from_fvg_layer_and_type():
    ohlc = [
        (99, 100, 98, 99),
        (99, 108, 99, 107),
        (107, 112, 110, 111),
        (111, 113, 111, 112),
    ]
    objs = fvg_to_chart_objects(_candles(ohlc), "BTCUSDT", "1h")
    assert objs
    assert all(o.layer == ChartObjectLayer.FVG for o in objs)
    assert all(o.type == ChartObjectType.RECTANGLE for o in objs)
    assert all(o.origin.get("kind") == "fvg" for o in objs)
