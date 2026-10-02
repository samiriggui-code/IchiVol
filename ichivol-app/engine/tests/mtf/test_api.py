"""MTF-1 — route GET /mtf/{symbol} : forme de réponse, lecture portefeuille, historique, erreurs."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from app.market_data import binance_futures
from tests.mtf.test_matrix import MONDAY, _FakeProvider, trend

client = TestClient(app)
P = settings.engine_api_prefix


def _patch_scan(monkeypatch):
    import time as _time

    from app.mtf.matrix import HORIZON_SECONDS

    monkeypatch.setattr(binance_futures, "fetch_open_interest_hist", lambda *a, **k: [])
    monkeypatch.setattr(binance_futures, "fetch_funding_rate_hist", lambda *a, **k: [])
    now = int(_time.time())

    def end_open(tf):
        if tf == "1w":
            return MONDAY + ((now - MONDAY) // 604800) * 604800
        return now - now % HORIZON_SECONDS[tf]

    provider = _FakeProvider()
    provider.fetch_ohlcv = lambda s, tf, limit=300: trend(tf, 300, end_open=end_open(tf), slope=0.4)
    candles = trend("1h", 300, end_open=end_open("1h"), slope=0.4)
    monkeypatch.setattr("app.screener.service.resolve_and_fetch",
                        lambda symbol, timeframe, limit=300, default_provider="binance": (provider, symbol, candles))
    return provider


def test_live_mtf_payload(monkeypatch):
    _patch_scan(monkeypatch)
    r = client.get(f"{P}/mtf/btcusdt", params={"timeframe": "1h"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["symbol"] == "BTCUSDT" and body["as_of"] is None and body["observe_only"] is True
    tfs = [h["timeframe"] for h in body["matrix"]["horizons"]]
    assert tfs == ["1h", "4h", "1d", "1w"]
    assert body["matrix"]["horizons"][0]["direction"] == body["pipeline"]["direction"]
    assert body["sentence"].startswith("Tendance 1h")
    if body["portfolio"] is not None:  # baseline portfolio exists in the test DB
        assert body["portfolio"]["allow_short"] is False
        assert body["portfolio"]["reading"].endswith(".")


def test_historical_mtf_has_no_pipeline_claim(monkeypatch):
    provider = _patch_scan(monkeypatch)

    class _R:
        pass

    def fake_resolve(symbol, default_provider="binance"):
        r = _R()
        r.provider, r.provider_symbol = provider, symbol
        return r

    monkeypatch.setattr("app.market_data.resolve.resolve", fake_resolve)
    import time as _time

    as_of = int(_time.time()) - 3 * 86400
    r = client.get(f"{P}/mtf/BTCUSDT", params={"timeframe": "1h", "as_of": as_of})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["pipeline"] is None and body["pipeline_reason"] == "historical_as_of_not_supported"
    for h in body["matrix"]["horizons"]:
        assert h["provisional_direction"] is None
        if h["bar_close"] is not None:
            assert h["bar_close"] <= as_of


def test_bad_timeframe_is_422():
    assert client.get(f"{P}/mtf/BTCUSDT", params={"timeframe": "1w"}).status_code == 422
