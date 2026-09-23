"""Golden parity — GET /context/{symbol} via REGISTRY."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app
from tests.indicators.test_ichimoku_lookahead import _make_candles

client = TestClient(app)
_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "context_indicators_golden.json"


@pytest.mark.parametrize("seed", [7, 42])
def test_context_indicators_matches_golden(seed: int, monkeypatch):
    candles = _make_candles(300, seed=seed)

    class _P:
        id = "binance"

    def fake_resolve(symbol, timeframe, limit=300, default_provider="binance"):
        return _P(), symbol, list(candles)

    monkeypatch.setattr("app.market_data.resolve.resolve_and_fetch", fake_resolve)
    resp = client.get(
        "/api/engine/context/BTCUSDT",
        params={"timeframe": "1h", "limit": 300},
    )
    assert resp.status_code == 200
    golden = json.loads(_FIXTURE.read_text(encoding="utf-8"))[f"seed_{seed}"]
    assert resp.json() == golden
