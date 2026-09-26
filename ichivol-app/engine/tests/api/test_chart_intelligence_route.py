"""API smoke for GET /chart-intelligence/{symbol}."""

from __future__ import annotations

import random

from fastapi.testclient import TestClient

from app.indicators.ichimoku import Candle
from app.main import app

client = TestClient(app)


def _candles(n: int = 160, seed: int = 11) -> list[Candle]:
    rng = random.Random(seed)
    price = 100.0
    out: list[Candle] = []
    for i in range(n):
        drift = rng.uniform(-1.2, 1.4)
        o = price
        c = max(1.0, price + drift)
        h = max(o, c) + 0.6
        l = min(o, c) - 0.6
        out.append(
            Candle(
                time=1_700_000_000 + i * 3600,
                open=o,
                high=h,
                low=l,
                close=c,
                volume=80 + rng.uniform(0, 40),
            )
        )
        price = c
    return out


def test_chart_intelligence_live_payload(monkeypatch):
    candles = _candles()

    def fake_resolve(symbol, timeframe, limit):
        class P:
            id = "test"

        return P(), symbol, candles[:limit]

    monkeypatch.setattr(
        "app.chart_intelligence.service.resolve_and_fetch", fake_resolve
    )
    resp = client.get(
        "/api/engine/chart-intelligence/BTCUSDT?timeframe=1h&limit=120&sources=engine"
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["symbol"] == "BTCUSDT"
    assert body["mock"] is False
    assert body["as_of"] == body["candles"][-1]["time"]
    assert len(body["candles"]) == 120
    assert isinstance(body["objects"], list)
    assert "ichimoku" in body and isinstance(body["ichimoku"], list)
    assert "projection" in body and isinstance(body["projection"], list)
    assert body["market_state"]["volatility"] in ("dead", "normal", "extreme")
    assert body["analysis"]["state"]
    assert body["replay"]["bar_seconds"] == 3600
    assert body["replay"]["first"] == body["candles"][0]["time"] or body["replay"]["first"] <= body["as_of"]


def test_chart_intelligence_as_of_truncates(monkeypatch):
    candles = _candles()
    cut = candles[99].time

    def fake_resolve(symbol, timeframe, limit):
        class P:
            id = "test"

        return P(), symbol, candles[:limit]

    monkeypatch.setattr(
        "app.chart_intelligence.service.resolve_and_fetch", fake_resolve
    )
    resp = client.get(
        f"/api/engine/chart-intelligence/BTCUSDT?timeframe=1h&limit=120&as_of={cut}&sources=engine"
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["as_of"] == cut
    assert all(c["time"] <= cut for c in body["candles"])
    assert body["replay"]["last"] == cut
