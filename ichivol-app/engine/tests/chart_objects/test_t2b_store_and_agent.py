"""T2b — chart overlay store + agent draw_* / get_structure."""

from __future__ import annotations

import random

import pytest
from fastapi.testclient import TestClient

from app.chart_objects.draw import build_from_draw_args
from app.chart_objects.store import (
    list_chart_objects,
    soft_delete_chart_object,
    upsert_chart_object,
)
from app.chart_objects.types import ChartObjectType
from app.db.session import SessionLocal
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


@pytest.fixture(autouse=True)
def _cleanup_t2b_overlays():
    yield
    session = SessionLocal()
    try:
        from app.db.models import ChartObjectOverlay

        rows = session.query(ChartObjectOverlay).filter(
            ChartObjectOverlay.symbol == "T2BTC"
        ).all()
        for row in rows:
            session.delete(row)
        session.commit()
    finally:
        session.close()


def test_build_horizontal_line_from_price_time():
    obj = build_from_draw_args(
        ChartObjectType.HORIZONTAL_LINE,
        {"symbol": "T2BTC", "timeframe": "1h", "price": 42.5, "time": 1_700_000_000},
    )
    assert obj.type == ChartObjectType.HORIZONTAL_LINE
    assert obj.source.value == "claude"
    assert obj.points[0].price == 42.5
    assert obj.id


def test_store_upsert_list_delete():
    obj = build_from_draw_args(
        ChartObjectType.MARKER,
        {
            "symbol": "T2BTC",
            "timeframe": "1h",
            "price": 100.0,
            "time": 1_700_000_000,
            "label": "pivot",
        },
    )
    session = SessionLocal()
    try:
        saved = upsert_chart_object(session, obj)
        session.commit()
        listed = list_chart_objects(
            session, symbol="T2BTC", timeframe="1h", sources=["claude"]
        )
        assert any(o.id == saved.id for o in listed)
        assert soft_delete_chart_object(session, saved.id)
        session.commit()
        listed2 = list_chart_objects(
            session, symbol="T2BTC", timeframe="1h", sources=["claude"]
        )
        assert all(o.id != saved.id for o in listed2)
    finally:
        session.close()


def test_agent_draw_horizontal_and_get_chart_objects(monkeypatch):
    candles = _candles()

    def fake_resolve(symbol, timeframe, limit):
        class P:
            id = "test"

        return P(), symbol, candles[:limit]

    monkeypatch.setattr("app.chart_objects.collect.resolve_and_fetch", fake_resolve)
    monkeypatch.setattr("app.structure.payload.resolve_and_fetch", fake_resolve)
    monkeypatch.setattr("app.agent_channel.commands.resolve_and_fetch", fake_resolve)

    draw = client.post(
        "/api/engine/agent/command",
        json={
            "cmd": "draw_horizontal_line",
            "args": {
                "symbol": "T2BTC",
                "timeframe": "1h",
                "price": 105.5,
                "time": candles[-1].time,
                "label": "R1",
            },
        },
    )
    assert draw.status_code == 200
    body = draw.json()
    assert body["ok"] is True
    oid = body["data"]["object"]["id"]
    assert body["data"]["object"]["source"] == "claude"

    got = client.post(
        "/api/engine/agent/command",
        json={
            "cmd": "get_chart_objects",
            "args": {"symbol": "T2BTC", "timeframe": "1h", "sources": "claude"},
        },
    )
    assert got.json()["ok"] is True
    ids = {o["id"] for o in got.json()["data"]["objects"]}
    assert oid in ids

    http = client.get(
        "/api/engine/chart-objects/T2BTC?timeframe=1h&sources=claude&limit=120"
    )
    assert http.status_code == 200
    assert any(o["id"] == oid for o in http.json()["objects"])

    deleted = client.post(
        "/api/engine/agent/command",
        json={"cmd": "delete_chart_object", "args": {"id": oid}},
    )
    assert deleted.json()["ok"] is True


def test_agent_get_structure(monkeypatch):
    candles = _candles()

    def fake_resolve(symbol, timeframe, limit):
        class P:
            id = "test"

        return P(), symbol, candles[:limit]

    monkeypatch.setattr("app.chart_objects.collect.resolve_and_fetch", fake_resolve)
    monkeypatch.setattr("app.structure.payload.resolve_and_fetch", fake_resolve)
    monkeypatch.setattr("app.agent_channel.commands.resolve_and_fetch", fake_resolve)
    resp = client.post(
        "/api/engine/agent/command",
        json={"cmd": "get_structure", "args": {"symbol": "BTCUSDT", "limit": 120}},
    )
    body = resp.json()
    assert body["ok"] is True
    assert "consensus" in body["data"]
    assert "detectors" in body["data"]


def test_draw_rejects_user_impersonation():
    resp = client.post(
        "/api/engine/agent/command",
        json={
            "cmd": "draw_marker",
            "args": {
                "symbol": "T2BTC",
                "price": 1.0,
                "time": 1_700_000_000,
                "source": "user",
            },
        },
    )
    assert resp.json()["ok"] is False
    assert "claude" in resp.json()["error"].lower()


def test_draw_rejects_engine_source():
    resp = client.post(
        "/api/engine/agent/command",
        json={
            "cmd": "draw_marker",
            "args": {
                "symbol": "T2BTC",
                "price": 1.0,
                "time": 1_700_000_000,
                "source": "engine",
            },
        },
    )
    assert resp.json()["ok"] is False


def test_http_merges_engine_and_claude(monkeypatch):
    candles = _candles()

    def fake_resolve(symbol, timeframe, limit):
        class P:
            id = "test"

        return P(), symbol, candles[:limit]

    monkeypatch.setattr("app.chart_objects.collect.resolve_and_fetch", fake_resolve)
    monkeypatch.setattr("app.agent_channel.commands.resolve_and_fetch", fake_resolve)

    draw = client.post(
        "/api/engine/agent/command",
        json={
            "cmd": "draw_horizontal_line",
            "args": {
                "symbol": "T2BTC",
                "timeframe": "1h",
                "price": 111.0,
                "time": candles[-1].time,
                "label": "HL",
            },
        },
    )
    oid = draw.json()["data"]["object"]["id"]

    http = client.get(
        "/api/engine/chart-objects/T2BTC?timeframe=1h&sources=engine,claude&limit=120"
    )
    assert http.status_code == 200
    body = http.json()
    sources = {o["source"] for o in body["objects"]}
    assert "claude" in sources
    assert any(o["id"] == oid for o in body["objects"])


def test_get_structure_parity_with_http(monkeypatch):
    candles = _candles()

    def fake_resolve(symbol, timeframe, limit):
        class P:
            id = "test"

        return P(), symbol, candles[:limit]

    monkeypatch.setattr("app.structure.payload.resolve_and_fetch", fake_resolve)
    monkeypatch.setattr("app.agent_channel.commands.resolve_and_fetch", fake_resolve)
    http = client.get("/api/engine/structure/BTCUSDT?timeframe=1h&limit=120")
    agent = client.post(
        "/api/engine/agent/command",
        json={"cmd": "get_structure", "args": {"symbol": "BTCUSDT", "limit": 120}},
    )
    assert http.status_code == 200
    assert agent.json()["ok"] is True
    assert agent.json()["data"] == http.json()


def test_delete_does_not_touch_user_overlay():
    from app.chart_objects.draw import build_from_draw_args
    from app.chart_objects.store import upsert_chart_object
    from app.chart_objects.types import ChartObjectType
    from app.db.session import SessionLocal

    user_obj = build_from_draw_args(
        ChartObjectType.MARKER,
        {
            "symbol": "T2BTC",
            "timeframe": "1h",
            "price": 50.0,
            "time": 1_700_000_000,
            "source": "user",
            "label": "mine",
        },
        agent_channel=False,
    )
    session = SessionLocal()
    try:
        saved = upsert_chart_object(session, user_obj)
        session.commit()
        uid = saved.id
    finally:
        session.close()

    deleted = client.post(
        "/api/engine/agent/command",
        json={"cmd": "delete_chart_object", "args": {"id": uid}},
    )
    assert deleted.json()["ok"] is False

    session = SessionLocal()
    try:
        from app.chart_objects.store import list_chart_objects

        listed = list_chart_objects(
            session, symbol="T2BTC", timeframe="1h", sources=["user"]
        )
        assert any(o.id == uid for o in listed)
    finally:
        session.close()


def test_draw_trend_line_with_points(monkeypatch):
    candles = _candles()

    def fake_resolve(symbol, timeframe, limit):
        class P:
            id = "test"

        return P(), symbol, candles[:limit]

    monkeypatch.setattr("app.agent_channel.commands.resolve_and_fetch", fake_resolve)
    resp = client.post(
        "/api/engine/agent/command",
        json={
            "cmd": "draw_trend_line",
            "args": {
                "symbol": "T2BTC",
                "timeframe": "1h",
                "points": [
                    {"time": candles[0].time, "price": candles[0].close},
                    {"time": candles[10].time, "price": candles[10].close},
                ],
            },
        },
    )
    assert resp.json()["ok"] is True
    obj = resp.json()["data"]["object"]
    assert obj["type"] == "trend_line"
    assert obj["source"] == "claude"
    assert len(obj["points"]) == 2
