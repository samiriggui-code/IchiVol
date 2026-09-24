"""Chart layer=breaks — StructureEvent BOS/CHoCH + breakout markers."""

from __future__ import annotations

from app.chart_objects.from_breaks import breaks_to_chart_objects
from app.chart_objects.from_structure import structure_to_chart_objects
from app.chart_objects.types import ChartObjectLayer
from app.indicators.ichimoku import Candle
from app.indicators.structure import StructureEventType, StructureParams
from app.structure.params import StructureEngineParams
from app.structure.service import detect_market_structure
from tests.structure.test_structure_engines import _make_candles


def _ohlc_candles(ohlc: list[tuple[float, float, float, float]]) -> list[Candle]:
    return [
        Candle(time=i, open=o, high=h, low=lo, close=c, volume=100.0)
        for i, (o, h, lo, c) in enumerate(ohlc)
    ]


def test_choch_event_emits_breaks_layer_marker():
    # Same fixture as test_t9b_choch.test_choch_when_break_against_bias
    ohlc = [
        (100, 105, 99, 104),
        (104, 110, 103, 108),
        (108, 130, 107, 125),
        (125, 126, 115, 118),
        (118, 120, 110, 112),
        (112, 114, 100, 102),
        (102, 108, 101, 106),
        (106, 110, 104, 108),
        (108, 122, 107, 120),
        (120, 121, 112, 114),
        (114, 116, 95, 98),
        (98, 102, 96, 100),
        (100, 104, 99, 103),
        (103, 125, 102, 124),
    ]
    candles = _ohlc_candles(ohlc)
    objs = breaks_to_chart_objects(
        candles,
        "BTCUSDT",
        "1h",
        params=StructureParams(
            swing_lookback=2,
            confirm_bars=5,
            confirm_displacement_atr=100.0,
        ),
    )
    events = [o for o in objs if o.origin.get("kind") == "structure_event"]
    assert events, "expected at least one StructureEvent marker"
    assert all(o.layer == ChartObjectLayer.BREAKS for o in events)
    choch = [o for o in events if o.subtype == "choch"]
    assert choch, "expected CHoCH marker"
    assert choch[0].label.startswith("CHoCH")
    assert choch[0].origin["event_type"] == StructureEventType.CHOCH.value


def test_structure_producer_no_longer_emits_breakouts():
    candles = _make_candles(120)
    snap = detect_market_structure(
        candles, StructureEngineParams(window_bars=120)
    )
    window = candles[-120:]
    struct = structure_to_chart_objects(snap, "BTCUSDT", "1h", window)
    assert all(
        o.origin.get("kind") != "breakout_candidate" for o in struct
    ), "breakouts must live on layer=breaks, not structure"


def test_breakouts_land_on_breaks_layer():
    candles = _make_candles(120)
    snap = detect_market_structure(
        candles, StructureEngineParams(window_bars=120)
    )
    window = candles[-120:]
    objs = breaks_to_chart_objects(
        window, "BTCUSDT", "1h", snapshot=snap
    )
    bos = [o for o in objs if o.origin.get("kind") == "breakout_candidate"]
    # May be empty on this seed — if present, must be breaks layer.
    for o in bos:
        assert o.layer == ChartObjectLayer.BREAKS
        assert o.subtype == "breakout"
