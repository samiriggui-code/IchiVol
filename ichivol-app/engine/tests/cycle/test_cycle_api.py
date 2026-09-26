"""API smoke for GET /cycle/{symbol} — mocked market data, no network."""

from __future__ import annotations

import math

from fastapi.testclient import TestClient

from app.indicators.ichimoku import Candle
from app.main import app

client = TestClient(app)

_T0 = 1_700_000_000
_TF = 3600


def _sine_candles(n: int = 200, period: float = 20.0) -> list[Candle]:
    base = 100.0
    out: list[Candle] = []
    for i in range(n):
        phase = 2.0 * math.pi * i / period
        price = base * math.exp(0.02 * math.sin(phase))
        t = _T0 + i * _TF
        out.append(
            Candle(time=t, open=price, high=price * 1.001, low=price * 0.999, close=price, volume=1.0)
        )
    return out


def test_get_cycle_observe_only(monkeypatch):
    candles = _sine_candles()

    class _Prov:
        id = "binance"

    def fake_resolve(symbol, timeframe, limit):
        return (_Prov(), symbol, candles[:limit])

    monkeypatch.setattr(
        "app.market_data.resolve.resolve_and_fetch",
        fake_resolve,
    )

    # now after last bar close
    now = _T0 + (len(candles) - 1) * _TF + _TF + 10
    res = client.get(
        f"/api/engine/cycle/BTCUSDT?timeframe=1h&limit=200&window=128&now={now}"
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["symbol"] == "BTCUSDT"
    assert "cycle" in body
    cyc = body["cycle"]
    assert "buy" not in cyc and "sell" not in cyc
    assert cyc["regime"] in {"TREND", "CYCLE", "TRANSITION", "NOISE"}
    assert "disclaimer" in body
    assert "not a trade signal" in body["disclaimer"].lower()


def test_get_cycle_drops_forming_bar(monkeypatch):
    candles = _sine_candles(50)

    class _Prov:
        id = "binance"

    def fake_resolve(symbol, timeframe, limit):
        return (_Prov(), symbol, candles[:limit])

    monkeypatch.setattr(
        "app.market_data.resolve.resolve_and_fetch",
        fake_resolve,
    )

    # Mid last bar → drop it
    last_open = _T0 + 49 * _TF
    now = last_open + _TF // 2
    res = client.get(
        f"/api/engine/cycle/BTCUSDT?timeframe=1h&limit=50&window=32&now={now}"
    )
    assert res.status_code == 200, res.text
    assert res.json()["n_bars"] == 49


def test_get_cycle_study_observe_only(monkeypatch):
    candles = _sine_candles(280)

    class _Prov:
        id = "binance"

    def fake_resolve(symbol, timeframe, limit):
        return (_Prov(), symbol, candles[:limit])

    monkeypatch.setattr(
        "app.market_data.resolve.resolve_and_fetch",
        fake_resolve,
    )

    now = _T0 + 279 * _TF + _TF + 10
    res = client.get(
        f"/api/engine/cycle/BTCUSDT/study?timeframe=1h&limit=280&window=96&horizon=8&now={now}"
    )
    assert res.status_code == 200, res.text
    body = res.json()
    assert body["study"]["ok"] is True
    assert body["study"]["verdict"]["promote_to_decision"] is False
    assert body["study"]["kind"] == "regime_filter_study"
    assert "Research" in body["disclaimer"]


def test_synthetic_validate_endpoint():
    res = client.get("/api/engine/cycle/synthetic/validate?window=128")
    assert res.status_code == 200, res.text
    assert res.json()["study"]["ok"] is True
