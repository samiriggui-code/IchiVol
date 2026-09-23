"""API tests for IndicatorRegistry routes."""

from __future__ import annotations

import json

from fastapi.testclient import TestClient

from app.indicators.ichimoku import Candle
from app.indicators.registry import REGISTRY
from app.main import app

client = TestClient(app)


class _FakeProvider:
    id = "binance"


def _candles(n: int) -> list[Candle]:
    return [
        Candle(
            time=1_700_000_000 + i * 3600,
            open=100 + i * 0.1,
            high=101 + i * 0.1,
            low=99 + i * 0.1,
            close=100.5 + i * 0.1,
            volume=100 + i,
        )
        for i in range(n)
    ]


def test_indicators_catalog():
    resp = client.get("/api/engine/indicators")
    assert resp.status_code == 200
    body = resp.json()
    assert "indicators" in body
    ids = {row["id"] for row in body["indicators"]}
    assert "ichimoku" in ids
    assert "rvol" in ids
    assert ids == set(REGISTRY.ids())
    for row in body["indicators"]:
        assert "primary_output" in row
        assert "warmup_default" in row
        assert "parameters" in row
        assert "outputs" in row


def test_indicator_series_warmup_and_limit(monkeypatch):
    captured: dict = {}

    def fake_resolve(symbol: str, timeframe: str, limit: int = 300, default_provider: str = "binance"):
        captured["limit"] = limit
        return _FakeProvider(), symbol, _candles(limit)

    monkeypatch.setattr(
        "app.market_data.resolve.resolve_and_fetch",
        fake_resolve,
    )

    limit = 50
    warmup = REGISTRY.get("rvol").warmup()
    resp = client.get(
        "/api/engine/indicators/rvol/BTCUSDT",
        params={"timeframe": "1h", "limit": limit},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert captured["limit"] == limit + warmup
    assert body["indicator"] == "rvol"
    assert body["symbol"] == "BTCUSDT"
    assert body["warmup"] == warmup
    assert body["primary_output"] == "rvol"
    assert len(body["series"]) == limit
    assert "rvol" in body["series"][-1]


def test_indicator_params_override(monkeypatch):
    def fake_resolve(symbol: str, timeframe: str, limit: int = 300, default_provider: str = "binance"):
        return _FakeProvider(), symbol, _candles(limit)

    monkeypatch.setattr("app.market_data.resolve.resolve_and_fetch", fake_resolve)

    resp = client.get(
        "/api/engine/indicators/rvol/ETHUSDT",
        params={"limit": 40, "params": json.dumps({"primary_window": 30})},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["params"]["primary_window"] == 30
    assert body["warmup"] == 30


def test_indicator_unknown_id_404(monkeypatch):
    monkeypatch.setattr(
        "app.market_data.resolve.resolve_and_fetch",
        lambda *a, **k: (_FakeProvider(), "X", _candles(10)),
    )
    resp = client.get("/api/engine/indicators/not_real/BTCUSDT")
    assert resp.status_code == 404


def test_indicator_invalid_params_422(monkeypatch):
    monkeypatch.setattr(
        "app.market_data.resolve.resolve_and_fetch",
        lambda *a, **k: (_FakeProvider(), "X", _candles(10)),
    )
    resp = client.get(
        "/api/engine/indicators/ppo/BTCUSDT",
        params={"params": json.dumps({"fast": 40, "slow": 10})},
    )
    assert resp.status_code == 422


def test_indicator_unknown_symbol_404(monkeypatch):
    def boom(*a, **k):
        raise ValueError("unknown_symbol: NOPE")

    monkeypatch.setattr("app.market_data.resolve.resolve_and_fetch", boom)
    resp = client.get("/api/engine/indicators/ichimoku/NOPE")
    assert resp.status_code == 404


def test_indicator_limit_bounds_422():
    """limit=0 / negative used to slice oddly (states[-0:] = full series)."""
    for bad in (0, -5):
        resp = client.get(
            "/api/engine/indicators/rvol/BTCUSDT",
            params={"limit": bad},
        )
        assert resp.status_code == 422, bad


def test_ichimoku_projection_keeps_warmup_for_window_start(monkeypatch):
    """Projection must compute on fetch (limit+warmup), not on candles[-limit:]."""
    limit = 300
    warmup = REGISTRY.get("ichimoku").warmup()
    captured: dict = {}

    def fake_resolve(symbol: str, timeframe: str, limit: int = 300, default_provider: str = "binance"):
        captured["limit"] = limit
        return _FakeProvider(), symbol, _candles(limit)

    monkeypatch.setattr("app.market_data.resolve.resolve_and_fetch", fake_resolve)

    resp = client.get(
        "/api/engine/indicators/ichimoku/BTCUSDT/projection",
        params={"timeframe": "1h", "limit": limit},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert captured["limit"] == limit + warmup
    assert body["kind"] == "projection"
    assert body["note"] == "display_only"
    assert body["warmup"] == warmup
    proj = body["projection"]
    assert proj
    # First visible candle time = time of candle at index warmup in the fetch
    # (fetch length = limit+warmup; window = last `limit` candles).
    window_start = 1_700_000_000 + warmup * 3600
    assert proj[0]["time_projected"] == window_start


def test_ichimoku_projection_invalid_params_422(monkeypatch):
    monkeypatch.setattr(
        "app.market_data.resolve.resolve_and_fetch",
        lambda *a, **k: (_FakeProvider(), "X", _candles(100)),
    )
    resp = client.get(
        "/api/engine/indicators/ichimoku/BTCUSDT/projection",
        params={"params": json.dumps({"senkouB": 52})},  # camelCase unknown
    )
    assert resp.status_code == 422


def test_location_nested_unknown_param_422(monkeypatch):
    monkeypatch.setattr(
        "app.market_data.resolve.resolve_and_fetch",
        lambda *a, **k: (_FakeProvider(), "X", _candles(120)),
    )
    resp = client.get(
        "/api/engine/indicators/location/BTCUSDT",
        params={"params": json.dumps({"volume_profile": {"foo": 1}})},
    )
    assert resp.status_code == 422
    detail = resp.json()["detail"]
    assert "location.volume_profile.foo" in detail


def test_location_nested_valid_params_200(monkeypatch):
    def fake_resolve(symbol: str, timeframe: str, limit: int = 300, default_provider: str = "binance"):
        return _FakeProvider(), symbol, _candles(limit)

    monkeypatch.setattr("app.market_data.resolve.resolve_and_fetch", fake_resolve)
    resp = client.get(
        "/api/engine/indicators/location/BTCUSDT",
        params={
            "timeframe": "1h",
            "limit": 80,
            "params": json.dumps({"volume_profile": {"num_bins": 10}}),
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["params"]["volume_profile"]["num_bins"] == 10
    assert len(body["series"]) == 80
