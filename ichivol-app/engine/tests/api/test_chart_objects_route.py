"""API smoke for GET /chart-objects/{symbol}."""

from __future__ import annotations

import random

from fastapi.testclient import TestClient

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
        out.append(Candle(time=1_700_000_000 + i * 3600, open=o, high=h, low=l, close=c, volume=100))
        price = c
    return out


def test_chart_objects_engine_source(monkeypatch):
    candles = _candles()

    def fake_resolve(symbol, timeframe, limit):
        class P:
            id = "test"

        return P(), symbol, candles[:limit]

    monkeypatch.setattr(
        "app.chart_objects.collect.resolve_and_fetch", fake_resolve
    )
    resp = client.get("/api/engine/chart-objects/BTCUSDT?timeframe=1h&limit=120&sources=engine")
    assert resp.status_code == 200
    body = resp.json()
    assert body["symbol"] == "BTCUSDT"
    assert body["as_of"] == candles[min(119, len(candles) - 1)].time
    assert isinstance(body["objects"], list)
    for o in body["objects"]:
        assert o["source"] == "engine"
        assert o["as_of"] == body["as_of"]


def test_chart_objects_non_engine_sources_empty(monkeypatch):
    def boom(*_a, **_k):
        raise AssertionError("should not fetch when engine not requested")

    monkeypatch.setattr("app.chart_objects.collect.resolve_and_fetch", boom)
    resp = client.get(
        "/api/engine/chart-objects/BTCUSDT?timeframe=1h&sources=user,claude"
    )
    assert resp.status_code == 200
    # Empty store → empty list (not an error). STRATEGY/BACKTEST also empty.
    assert resp.json()["objects"] == []


def test_chart_objects_strategy_source_empty(monkeypatch):
    def boom(*_a, **_k):
        raise AssertionError("should not fetch when engine not requested")

    monkeypatch.setattr("app.chart_objects.collect.resolve_and_fetch", boom)
    resp = client.get(
        "/api/engine/chart-objects/BTCUSDT?timeframe=1h&sources=strategy,backtest"
    )
    assert resp.status_code == 200
    assert resp.json()["objects"] == []
