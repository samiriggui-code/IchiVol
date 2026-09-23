"""T2b — agent draws must be grounded on real OHLCV (anti-hallucination)."""

from __future__ import annotations

import random

import pytest
from fastapi.testclient import TestClient

from app.agent_channel.commands import CommandError, _draw_and_persist
from app.chart_objects.from_structure import structure_to_chart_objects
from app.chart_objects.grounding import assert_object_grounded
from app.chart_objects.types import (
    ChartObject,
    ChartObjectSource,
    ChartObjectType,
    ChartPoint,
)
from app.indicators.ichimoku import Candle
from app.main import app

client = TestClient(app)


def _candles(n: int = 120, seed: int = 7) -> list[Candle]:
    rng = random.Random(seed)
    price = 100.0
    out: list[Candle] = []
    for i in range(n):
        drift = rng.uniform(-1.0, 1.0)
        o = price
        c = max(1.0, price + drift)
        h = max(o, c) + 0.5
        l = min(o, c) - 0.5
        out.append(
            Candle(
                time=1_700_000_000 + i * 3600,
                open=o,
                high=h,
                low=l,
                close=c,
                volume=100,
            )
        )
        price = c
    return out


@pytest.fixture
def candles() -> list[Candle]:
    return _candles()


@pytest.fixture
def patch_fetch(monkeypatch, candles):
    def fake_resolve(symbol, timeframe, limit):
        class P:
            id = "test"

        return P(), symbol, candles[:limit]

    monkeypatch.setattr(
        "app.agent_channel.commands.resolve_and_fetch", fake_resolve
    )
    monkeypatch.setattr(
        "app.chart_objects.collect.resolve_and_fetch", fake_resolve
    )
    monkeypatch.setattr(
        "app.structure.payload.resolve_and_fetch", fake_resolve
    )
    return candles


def test_grounding_rejects_price_100x(candles):
    hi = max(c.high for c in candles)
    obj = ChartObject(
        type=ChartObjectType.HORIZONTAL_LINE,
        source=ChartObjectSource.CLAUDE,
        symbol="T2BTC",
        timeframe="1h",
        points=(ChartPoint(time=candles[-1].time, price=hi * 100),),
        as_of=candles[-1].time,
        origin={"via": "test"},
    )
    with pytest.raises(ValueError, match="point_not_grounded"):
        assert_object_grounded(obj, candles)


def test_grounding_rejects_future_time_beyond_projected(candles):
    step = candles[-1].time - candles[-2].time
    far = candles[-1].time + step * 50
    obj = ChartObject(
        type=ChartObjectType.TREND_LINE,
        source=ChartObjectSource.CLAUDE,
        symbol="T2BTC",
        timeframe="1h",
        points=(
            ChartPoint(time=candles[-10].time, price=candles[-10].close),
            ChartPoint(time=far, price=candles[-1].close),
        ),
        as_of=candles[-1].time,
        origin={"via": "test", "projected": True},
    )
    with pytest.raises(ValueError, match="point_not_grounded"):
        assert_object_grounded(obj, candles)


def test_grounding_accepts_zone_on_series(candles):
    lo = min(c.low for c in candles[-50:])
    hi = max(c.high for c in candles[-50:])
    obj = ChartObject(
        type=ChartObjectType.ZONE,
        source=ChartObjectSource.CLAUDE,
        symbol="T2BTC",
        timeframe="1h",
        points=(),
        as_of=candles[-1].time,
        price_low=lo,
        price_high=hi,
        origin={"via": "test"},
    )
    assert_object_grounded(obj, candles)


def test_draw_horizontal_price_100x_rejected_via_agent(patch_fetch, candles):
    hi = max(c.high for c in candles)
    with pytest.raises(CommandError, match="point_not_grounded"):
        _draw_and_persist(
            "horizontal_line",
            {
                "symbol": "T2BTC",
                "timeframe": "1h",
                "price": hi * 100,
                "time": candles[-1].time,
            },
        )


def test_draw_trend_future_beyond_proj_rejected(patch_fetch, candles):
    step = candles[-1].time - candles[-2].time
    far = candles[-1].time + step * 50
    with pytest.raises(CommandError, match="point_not_grounded"):
        _draw_and_persist(
            "trend_line",
            {
                "symbol": "T2BTC",
                "timeframe": "1h",
                "projected": True,
                "points": [
                    {"time": candles[-10].time, "price": candles[-10].close},
                    {"time": far, "price": candles[-1].close},
                ],
            },
        )


def test_draw_zone_coherent_accepted(patch_fetch, candles):
    lo = min(c.low for c in candles[-50:])
    hi = max(c.high for c in candles[-50:])
    out = _draw_and_persist(
        "zone",
        {
            "symbol": "T2BTC",
            "timeframe": "1h",
            "price_low": lo,
            "price_high": hi,
            "as_of": candles[-1].time,
        },
    )
    assert out["upserted"] is True
    assert out["object"]["type"] == "zone"


def test_structure_derived_objects_still_ground(patch_fetch, candles):
    """Normal agent path: structure endpoints → coords stay on the series."""
    from app.structure.service import detect_market_structure

    report = detect_market_structure(candles, include_pytrendline=False)
    objs = structure_to_chart_objects(report, "T2BTC", "1h", candles)
    for obj in objs:
        assert_object_grounded(obj, candles)

    if objs:
        sample = objs[0]
        if sample.points:
            pt = sample.points[0]
            out = _draw_and_persist(
                "horizontal_line",
                {
                    "symbol": "T2BTC",
                    "timeframe": "1h",
                    "price": pt.price,
                    "time": pt.time,
                    "label": "from_structure",
                },
            )
            assert out["upserted"] is True


def test_existing_agent_draw_still_ok_with_grounding(patch_fetch, candles):
    resp = client.post(
        "/api/engine/agent/command",
        json={
            "cmd": "draw_horizontal_line",
            "args": {
                "symbol": "T2BTC",
                "timeframe": "1h",
                "price": candles[-1].close,
                "time": candles[-1].time,
                "label": "R1",
            },
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
