"""T2a — ChartObject model, structure producer, selection parity, causality."""

from __future__ import annotations

import pytest

from app.api.common import _line_dict, _zone_dict
from app.chart_objects.from_structure import (
    MAX_TRENDLINES_PER_SIDE,
    MAX_ZONES_PER_SIDE,
    structure_to_chart_objects,
)
from app.chart_objects.types import (
    ChartObject,
    ChartObjectSource,
    ChartObjectType,
    ChartPoint,
)
from app.structure.params import StructureEngineParams
from app.structure.service import detect_market_structure
from tests.structure.test_structure_engines import _make_candles


def _base_kwargs(**overrides):
    kw = dict(
        type=ChartObjectType.MARKER,
        source=ChartObjectSource.ENGINE,
        symbol="btcusdt",
        timeframe="1h",
        points=(ChartPoint(time=100, price=42.5),),
        as_of=100,
        confidence=0.5,
        origin={"kind": "test"},
    )
    kw.update(overrides)
    return kw


def test_round_trip_to_dict_from_dict():
    obj = ChartObject(**_base_kwargs(label="BO", side="resistance", subtype="breakout"))
    restored = ChartObject.from_dict(obj.to_dict())
    assert restored.to_dict() == obj.to_dict()
    assert restored.id == obj.id


def test_id_stable_same_input():
    a = ChartObject(**_base_kwargs())
    b = ChartObject(**_base_kwargs())
    assert a.id == b.id
    assert len(a.id) == 24


def test_id_changes_with_coords():
    a = ChartObject(**_base_kwargs())
    b = ChartObject(
        **_base_kwargs(points=(ChartPoint(time=100, price=42.5 + 1e-10),))
    )
    # Rounded to 8 decimals → same id
    assert a.id == b.id
    c = ChartObject(**_base_kwargs(points=(ChartPoint(time=100, price=43.0),)))
    assert c.id != a.id


def test_validation_trend_line_needs_two_points():
    with pytest.raises(ValueError, match="TREND_LINE requires exactly 2"):
        ChartObject(
            **_base_kwargs(
                type=ChartObjectType.TREND_LINE,
                points=(ChartPoint(time=1, price=1.0),),
            )
        )


def test_validation_zone_price_order():
    with pytest.raises(ValueError, match="price_low < price_high"):
        ChartObject(
            **_base_kwargs(
                type=ChartObjectType.ZONE,
                points=(),
                price_low=10.0,
                price_high=10.0,
            )
        )


def test_validation_marker_one_point():
    with pytest.raises(ValueError, match="MARKER requires exactly 1"):
        ChartObject(**_base_kwargs(points=()))


def test_causality_point_after_as_of_rejected():
    with pytest.raises(ValueError, match="projected"):
        ChartObject(
            **_base_kwargs(
                type=ChartObjectType.TREND_LINE,
                points=(
                    ChartPoint(time=10, price=1.0),
                    ChartPoint(time=20, price=2.0),
                ),
                as_of=15,
            )
        )


def test_causality_projected_extension_allowed():
    obj = ChartObject(
        **_base_kwargs(
            type=ChartObjectType.TREND_LINE,
            points=(
                ChartPoint(time=10, price=1.0),
                ChartPoint(time=20, price=2.0),
            ),
            as_of=15,
            origin={"kind": "structure_trendline", "projected": True},
        )
    )
    assert obj.origin["projected"] is True


def _structure_api_shape(snap, window):
    """Mirror GET /structure response fields used by toStructureOverlay."""
    return {
        "consensus": {
            "support_zones": [_zone_dict(z) for z in snap.consensus.support_zones],
            "resistance_zones": [_zone_dict(z) for z in snap.consensus.resistance_zones],
        },
        "detectors": {
            name: {
                "support_trendlines": [_line_dict(t, window) for t in ms.support_trendlines],
                "resistance_trendlines": [_line_dict(t, window) for t in ms.resistance_trendlines],
            }
            for name, ms in snap.by_detector.items()
        },
    }


def _to_structure_overlay(payload: dict) -> dict:
    """Python port of structure.ts toStructureOverlay (selection only)."""

    def top(rows, n):
        return sorted(rows, key=lambda r: r["score"], reverse=True)[:n]

    def has_points(t):
        return (
            t.get("start_time") is not None
            and t.get("end_time") is not None
            and t.get("start_price") is not None
            and t.get("end_price") is not None
            and t["end_time"] > t["start_time"]
        )

    zones = top(payload["consensus"]["support_zones"], MAX_ZONES_PER_SIDE) + top(
        payload["consensus"]["resistance_zones"], MAX_ZONES_PER_SIDE
    )
    all_lines = []
    for d in payload["detectors"].values():
        all_lines.extend(d["support_trendlines"])
        all_lines.extend(d["resistance_trendlines"])
    drawable = [t for t in all_lines if has_points(t)]
    trendlines = top(
        [t for t in drawable if t["side"] == "support"], MAX_TRENDLINES_PER_SIDE
    ) + top([t for t in drawable if t["side"] == "resistance"], MAX_TRENDLINES_PER_SIDE)
    return {"zones": zones, "trendlines": trendlines}


@pytest.mark.parametrize("seed", [7, 42])
def test_selection_parity_with_to_structure_overlay(seed: int):
    candles = _make_candles(300, seed=seed)
    params = StructureEngineParams(window_bars=300)
    snap = detect_market_structure(candles, params, include_pytrendline=False)
    window = list(candles[-params.window_bars :])
    payload = _structure_api_shape(snap, window)
    expected = _to_structure_overlay(payload)

    objs = structure_to_chart_objects(snap, "BTCUSDT", "1h", window)
    zones = [o for o in objs if o.type == ChartObjectType.ZONE]
    lines = [o for o in objs if o.type == ChartObjectType.TREND_LINE]

    assert len(zones) == len(expected["zones"])
    for got, want in zip(zones, expected["zones"]):
        assert got.side == want["side"]
        assert abs(got.price_low - want["low"]) < 1e-9
        assert abs(got.price_high - want["high"]) < 1e-9
        assert got.origin["touch_count"] == want["touch_count"]
        assert got.label == f"{'S' if want['side'] == 'support' else 'R'} ×{want['touch_count']}"

    assert len(lines) == len(expected["trendlines"])
    for got, want in zip(lines, expected["trendlines"]):
        assert got.side == want["side"]
        assert got.points[0].time == want["start_time"]
        assert got.points[1].time == want["end_time"]
        assert abs(got.points[0].price - want["start_price"]) < 1e-9
        assert abs(got.points[1].price - want["end_price"]) < 1e-9


@pytest.mark.parametrize("seed", [7, 42])
def test_causality_as_of_and_points(seed: int):
    candles = _make_candles(300, seed=seed)
    params = StructureEngineParams(window_bars=300)
    snap = detect_market_structure(candles, params, include_pytrendline=False)
    window = list(candles[-params.window_bars :])
    as_of = int(window[-1].time)
    objs = structure_to_chart_objects(snap, "BTCUSDT", "1h", window)
    assert objs, "expected some chart objects on synthetic seeds"
    for o in objs:
        assert o.as_of == as_of
        projected = bool(o.origin.get("projected"))
        for p in o.points:
            if projected:
                continue
            assert p.time <= as_of, f"{o.type} point {p.time} > as_of {as_of}"
