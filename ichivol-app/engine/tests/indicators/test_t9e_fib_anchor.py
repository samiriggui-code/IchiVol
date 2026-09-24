"""T9e — Fib anchored on ImpulseEvent; naive fallback; anti-lookahead."""

from __future__ import annotations

from app.chart_objects.from_fibonacci import fibonacci_to_chart_objects
from app.chart_objects.types import ChartObjectLayer, ChartObjectType
from app.fibonacci.context import compute_fib_context, swings_from_impulse
from app.indicators.impulse import ImpulseEvent, ImpulseParams, compute_impulse
from app.indicators.structure import StructureParams, compute_structure
from tests.indicators.test_ichimoku_lookahead import _make_candles


def test_swings_from_impulse_bullish_and_bearish():
    bull = ImpulseEvent(
        direction="bullish",
        start_bar=1,
        end_bar=5,
        start_price=100.0,
        end_price=120.0,
        bar=7,
        displacement_atr=2.0,
        rvol=None,
    )
    assert swings_from_impulse(bull) == (100.0, 120.0, "up")
    bear = ImpulseEvent(
        direction="bearish",
        start_bar=1,
        end_bar=5,
        start_price=120.0,
        end_price=100.0,
        bar=7,
        displacement_atr=2.0,
        rvol=None,
    )
    assert swings_from_impulse(bear) == (100.0, 120.0, "down")


def test_naive_default_unchanged_for_gate_compat():
    candles = _make_candles(200, seed=7)
    naive = compute_fib_context(candles)  # default anchor=naive
    explicit = compute_fib_context(candles, anchor="naive")
    if naive is None:
        assert explicit is None
        return
    assert naive.swing_low == explicit.swing_low
    assert naive.swing_high == explicit.swing_high
    assert naive.impulse == explicit.impulse
    assert naive.anchor_source == "naive_pivots"


def test_impulse_anchor_when_active():
    candles = _make_candles(120, seed=17)
    params = ImpulseParams(swing_lookback=2, min_displacement_atr=0.5)
    states = compute_impulse(candles, params)
    active = states[-1].active
    if active is None:
        # Lower threshold until we get an active impulse
        params = ImpulseParams(swing_lookback=2, min_displacement_atr=0.01)
        states = compute_impulse(candles, params)
        active = states[-1].active
    assert active is not None
    ctx = compute_fib_context(candles, anchor="impulse", impulse_params=params)
    assert ctx is not None
    assert ctx.anchor_source == "impulse_event"
    expected = swings_from_impulse(active)
    assert expected is not None
    assert ctx.swing_low == expected[0]
    assert ctx.swing_high == expected[1]
    assert ctx.impulse == expected[2]
    assert ctx.known_bar == active.bar


def test_fib_impulse_anti_lookahead():
    candles = _make_candles(100, seed=19)
    params = ImpulseParams(swing_lookback=2, min_displacement_atr=0.01)
    states = compute_impulse(candles, params)
    events = [s for s in states if s.event is not None]
    assert events
    for s in events:
        b = s.event.bar
        # Truncation before known bar must not see this impulse as active
        trunc = compute_fib_context(
            candles[:b], anchor="impulse", impulse_params=params
        )
        if trunc is not None:
            assert trunc.known_bar is None or trunc.known_bar < b
            assert not (
                trunc.start_bar == s.event.start_bar
                and trunc.end_bar == s.event.end_bar
                and trunc.known_bar == b
            )
        inclusive = compute_fib_context(
            candles[: b + 1], anchor="impulse", impulse_params=params
        )
        assert inclusive is not None
        assert inclusive.known_bar == b


def test_fib_does_not_change_structure():
    candles = _make_candles(80, seed=23)
    s1 = [x.bos for x in compute_structure(candles, StructureParams())]
    _ = compute_fib_context(candles, anchor="auto")
    s2 = [x.bos for x in compute_structure(candles, StructureParams())]
    assert s1 == s2


def test_from_fibonacci_layer():
    candles = _make_candles(120, seed=11)
    objs = fibonacci_to_chart_objects(
        candles,
        "BTCUSDT",
        "1h",
        impulse_params=ImpulseParams(min_displacement_atr=0.01),
        key_only=True,
    )
    if not objs:
        # rare on some seeds — still valid empty
        return
    assert all(o.layer == ChartObjectLayer.FIBONACCI for o in objs)
    assert all(o.type == ChartObjectType.HORIZONTAL_LINE for o in objs)
    assert all(o.origin.get("kind") == "fibonacci" for o in objs)
