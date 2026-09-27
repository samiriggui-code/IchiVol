"""Liquidity (BSL/SSL) + confluence zone producers."""

from __future__ import annotations

from app.chart_objects.from_confluence import confluence_to_chart_objects
from app.chart_objects.from_fvg import fvg_to_chart_objects
from app.chart_objects.from_liquidity import liquidity_to_chart_objects
from app.chart_objects.from_structure import structure_to_chart_objects
from app.chart_objects.types import ChartObjectLayer
from app.indicators.ichimoku import Candle
from app.structure.params import StructureEngineParams
from app.structure.service import detect_market_structure


def _candles_equal_highs() -> list[Candle]:
    """Series with two equal swing highs near 110 → BSL candidate."""
    rows: list[tuple[float, float, float, float]] = [
        (100, 102, 99, 101),
        (101, 105, 100, 104),
        (104, 110, 103, 108),  # high pivot ~110
        (108, 109, 104, 105),
        (105, 106, 100, 101),
        (101, 103, 99, 100),
        (100, 104, 99, 103),
        (103, 110, 102, 107),  # second high ~110
        (107, 108, 103, 104),
        (104, 105, 101, 102),
        (102, 103, 100, 101),
        (101, 102, 99, 100),
        (100, 101, 98, 99),
        (99, 100, 97, 98),
        (98, 99, 96, 97),
        (97, 98, 95, 96),
    ]
    return [
        Candle(time=1_700_000_000 + i * 3600, open=o, high=h, low=lo, close=c, volume=1_000.0)
        for i, (o, h, lo, c) in enumerate(rows)
    ]


def test_liquidity_emits_bsl_or_ssl_layer():
    candles = _candles_equal_highs()
    objs = liquidity_to_chart_objects(candles, "ETHUSDT", "1h")
    assert objs, "expected at least one liquidity pool"
    assert all(o.layer == ChartObjectLayer.LIQUIDITY for o in objs)
    assert all(o.origin.get("kind") == "liquidity" for o in objs)
    assert all(o.origin.get("producer") == "liquidity_engine" for o in objs)
    assert any(o.label in ("BSL", "SSL") for o in objs)


def test_confluence_overlap_marks_score_mock():
    candles = _candles_equal_highs()
    # Pad a bit more structure-friendly bars
    base = list(candles)
    for i in range(20):
        t = base[-1].time + 3600
        c = base[-1].close
        base.append(
            Candle(time=t, open=c, high=c + 2, low=c - 2, close=c + 0.5, volume=800.0)
        )
    snap = detect_market_structure(base, StructureEngineParams(window_bars=min(len(base), 80)))
    objs = []
    objs.extend(structure_to_chart_objects(snap, "ETHUSDT", "1h", base))
    objs.extend(fvg_to_chart_objects(base, "ETHUSDT", "1h"))
    objs.extend(liquidity_to_chart_objects(base, "ETHUSDT", "1h"))
    conf = confluence_to_chart_objects(base, "ETHUSDT", "1h", objs)
    # May be empty if no multi-layer overlap — when present, must be honest mock.
    for o in conf:
        assert o.layer == ChartObjectLayer.CONFLUENCE
        assert o.origin.get("score_is_mock") is True
        assert o.origin.get("kind") == "confluence"
        assert o.origin.get("components")
