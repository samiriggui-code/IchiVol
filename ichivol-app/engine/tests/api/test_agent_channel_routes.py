"""Agent command channel (READ v1) -- GET /agent/tools, GET /agent/capabilities,
POST /agent/command, POST /agent/batch. Every command wraps an
already-tested engine function, so these tests focus on the channel's own
contract (allowlist, error isolation, order-stability, batch cap) rather
than re-proving indicator/pipeline correctness covered elsewhere.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.agent_channel.registry import TOOLS
from app.indicators.ichimoku import Candle
from app.main import app
from app.market_data import binance, binance_futures
from app.screener import cache as cache_module

client = TestClient(app)


@pytest.fixture(autouse=True)
def _no_live_oi_funding_calls(monkeypatch):
    monkeypatch.setattr(binance_futures, "fetch_open_interest_hist", lambda *a, **k: [])
    monkeypatch.setattr(binance_futures, "fetch_funding_rate_hist", lambda *a, **k: [])


@pytest.fixture(autouse=True)
def _no_contamination_of_the_real_paper_portfolio(monkeypatch):
    # scan_market forces a cache refresh with fixture data in one test below
    # -- same real-DB contamination risk as tests/api/test_routes.py's
    # equivalent fixture, same fix.
    monkeypatch.setattr(cache_module.paper_engine, "sync_auto_watchlist", lambda session, rows: [])


def _uptrend_with_spike(n: int) -> list[Candle]:
    volumes = [50.0] * (n - 1) + [250.0]
    return [
        Candle(time=i, open=100 + i, high=101 + i, low=99 + i, close=100.5 + i, volume=volumes[i])
        for i in range(n)
    ]


def test_agent_tools_lists_the_full_v1_allowlist():
    resp = client.get("/api/engine/agent/tools")
    assert resp.status_code == 200
    names = {t["name"] for t in resp.json()["tools"]}
    assert names == set(TOOLS.keys())
    assert all(t["read_only"] for t in resp.json()["tools"])


def test_agent_capabilities_is_a_read_only_stub():
    resp = client.get("/api/engine/agent/capabilities")
    assert resp.status_code == 200
    body = resp.json()
    assert body["read_only"] is True
    assert body["write_tier_enabled"] is False
    assert body["max_batch_items"] == 20
    assert set(body["commands"]) == set(TOOLS.keys())


def test_agent_command_rejects_an_unknown_command():
    resp = client.post("/api/engine/agent/command", json={"cmd": "delete_everything", "args": {}})
    assert resp.status_code == 200  # the channel itself never 500s/errors HTTP-wise
    body = resp.json()
    assert body["ok"] is False
    assert "unknown_command" in body["error"]


def test_agent_command_reports_a_missing_required_arg_as_a_clean_error():
    resp = client.post("/api/engine/agent/command", json={"cmd": "get_symbol_context", "args": {}})
    body = resp.json()
    assert body["ok"] is False
    assert "missing_or_invalid_arg" in body["error"]


def test_agent_command_scan_market(monkeypatch):
    # scan_market serves whatever is in the cache -- pre-populate it directly
    # instead of forcing a real cold refresh (which would fan out to every
    # provider in the default watchlist, including biquote/twelve_data, and
    # cost real network timeouts for anything not mocked here).
    import time

    from app.agents.types import Direction, StrategyAgentOutput
    from app.decision.combiner import DecisionResult
    from app.decision.pipeline import PipelineResult
    from app.indicators.atr import AtrState, VolatilityRegime
    from app.screener.cache import CacheEntry
    from app.screener.service import ScreenerRow

    fake_atr = AtrState(
        time=0, true_range=1.0, atr=1.0, percentile=0.5,
        regime=VolatilityRegime.NORMAL, suggested_stop_distance=1.5,
    )
    fake_ichimoku = StrategyAgentOutput(
        agent="ICHIMOKU_AGENT", direction=Direction.LONG, probability=0.6, confidence=0.5,
        expected_value=0.0, reasons=[], invalidation=[], metadata={"score": 10.0},
    )
    fake_rvol = StrategyAgentOutput(
        agent="RVOL_AGENT", direction=Direction.NEUTRAL, probability=0.5, confidence=0.5,
        expected_value=0.0, reasons=[], invalidation=[], metadata={"rvol": 1.0},
    )
    fake_decision = DecisionResult(
        strategy_version="test", decision="WATCH", direction=Direction.LONG,
        probability=0.6, confidence=0.5, agreement=0.5,
    )
    fake_row = ScreenerRow(
        symbol="BTCUSDT", exchange="binance", timeframe="1h", price=100.0,
        candles=[], ichimoku=fake_ichimoku, rvol=fake_rvol, decision=fake_decision,
        pipeline=PipelineResult(decision="WATCH", direction=Direction.LONG, stages=[]),
        atr=fake_atr,
    )
    cache_module.screener_cache._entry = CacheEntry(rows=[fake_row], computed_at=time.time(), timeframe="1h")

    resp = client.post("/api/engine/agent/command", json={"cmd": "scan_market", "args": {}})
    body = resp.json()
    assert body["ok"] is True
    assert body["cmd"] == "scan_market"
    assert len(body["data"]["rows"]) == 1
    assert body["data"]["rows"][0]["symbol"] == "BTCUSDT"
    assert "risk" in body["data"]["rows"][0]

    cache_module.screener_cache._entry = None


def test_agent_command_get_symbol_context(monkeypatch):
    candles = _uptrend_with_spike(160)
    monkeypatch.setattr(binance, "fetch_klines", lambda symbol, tf, limit: candles)

    resp = client.post(
        "/api/engine/agent/command",
        json={"cmd": "get_symbol_context", "args": {"symbol": "BTCUSDT", "persist": False}},
    )
    body = resp.json()["data"]
    assert body["symbol"] == "BTCUSDT"
    assert body["decision"] == "STRONG_BUY"
    assert "reasons" in body and "pipeline" in body


def test_agent_command_detect_signal_is_condensed(monkeypatch):
    candles = _uptrend_with_spike(160)
    monkeypatch.setattr(binance, "fetch_klines", lambda symbol, tf, limit: candles)

    resp = client.post(
        "/api/engine/agent/command", json={"cmd": "detect_signal", "args": {"symbol": "BTCUSDT"}}
    )
    body = resp.json()["data"]
    assert set(body) == {"symbol", "timeframe", "price", "decision", "direction", "stages", "risk"}


def test_agent_command_compare_timeframes_isolates_a_bad_timeframe(monkeypatch):
    candles = _uptrend_with_spike(160)

    def _fake_fetch(symbol, tf, limit):
        if tf == "4h":
            return []  # simulate insufficient history on this one timeframe
        return candles

    monkeypatch.setattr(binance, "fetch_klines", _fake_fetch)

    resp = client.post(
        "/api/engine/agent/command",
        json={"cmd": "compare_timeframes", "args": {"symbol": "BTCUSDT", "timeframes": ["1h", "4h"]}},
    )
    body = resp.json()["data"]
    assert body["timeframes"]["1h"]["decision"] == "STRONG_BUY"
    assert "error" in body["timeframes"]["4h"]


def test_agent_command_run_backtest(monkeypatch):
    candles = _uptrend_with_spike(300)
    monkeypatch.setattr(binance, "fetch_klines", lambda symbol, tf, limit: candles)

    resp = client.post(
        "/api/engine/agent/command",
        json={"cmd": "run_backtest", "args": {"symbol": "BTCUSDT", "limit": 300}},
    )
    body = resp.json()["data"]
    # Not hardcoding the exact experiment set here (it evolves as new gates
    # get promoted -- see tests/api/test_routes.py::test_backtest_endpoint_shape
    # for the source of truth on what's currently registered): this command
    # just needs to prove it relays experiments.compare()'s real output
    # unchanged, so assert the shape/keys of whatever comes back instead.
    assert "PIPELINE" in body["experiments"]
    for exp in body["experiments"].values():
        assert "metrics" in exp and "backtest" in exp


def test_agent_command_calculate_ichimoku_and_rvol_return_raw_indicators_only(monkeypatch):
    candles = _uptrend_with_spike(160)
    monkeypatch.setattr(binance, "fetch_klines", lambda symbol, tf, limit: candles)

    ichi = client.post(
        "/api/engine/agent/command", json={"cmd": "calculate_ichimoku", "args": {"symbol": "BTCUSDT"}}
    ).json()["data"]
    assert "tenkan" in ichi and "decision" not in ichi

    rvol = client.post(
        "/api/engine/agent/command", json={"cmd": "calculate_rvol", "args": {"symbol": "BTCUSDT"}}
    ).json()["data"]
    assert "anomaly_level" in rvol and "decision" not in rvol


def test_agent_command_get_correlations(monkeypatch):
    candles = _uptrend_with_spike(160)
    monkeypatch.setattr(binance, "fetch_klines", lambda symbol, tf, limit: candles)

    resp = client.post(
        "/api/engine/agent/command",
        json={"cmd": "get_correlations", "args": {"symbols": ["BTCUSDT", "ETHUSDT"]}},
    )
    body = resp.json()["data"]
    assert set(body["symbols"]) == {"BTCUSDT", "ETHUSDT"}


def test_agent_command_get_news(monkeypatch):
    import httpx

    from app.context import news as news_module

    xml = (
        '<?xml version="1.0"?><rss><channel>'
        "<item><title>T</title><link>https://x.example/1</link>"
        "<pubDate>Wed, 16 Sep 2026 12:00:00 GMT</pubDate></item>"
        "</channel></rss>"
    )

    class FakeResp:
        text = xml

        def raise_for_status(self) -> None:
            return None

    monkeypatch.setattr(news_module.httpx, "get", lambda *a, **k: FakeResp())
    news_module._cache.clear()

    resp = client.post(
        "/api/engine/agent/command", json={"cmd": "get_news", "args": {"sources": ["coindesk"]}}
    )
    body = resp.json()["data"]
    assert body["items"][0]["title"] == "T"
    news_module._cache.clear()


def test_agent_command_get_calendar(monkeypatch):
    from app.context import calendar as calendar_module

    class FakeResp:
        def raise_for_status(self) -> None:
            return None

        def json(self):
            return [{"title": "CPI", "country": "USD", "date": "2026-09-17", "impact": "High"}]

    monkeypatch.setattr(calendar_module.httpx, "get", lambda *a, **k: FakeResp())
    calendar_module._cache = None

    resp = client.post("/api/engine/agent/command", json={"cmd": "get_calendar", "args": {}})
    body = resp.json()["data"]
    assert body["events"][0]["title"] == "CPI"
    calendar_module._cache = None


def test_context_news_route(monkeypatch):
    from app.context import news as news_module

    class FakeResp:
        text = (
            '<?xml version="1.0"?><rss><channel>'
            "<item><title>Headline</title><link>https://x.example/2</link></item>"
            "</channel></rss>"
        )

        def raise_for_status(self) -> None:
            return None

    monkeypatch.setattr(news_module.httpx, "get", lambda *a, **k: FakeResp())
    news_module._cache.clear()

    resp = client.get("/api/engine/context/news")
    assert resp.status_code == 200
    assert resp.json()["items"][0]["title"] == "Headline"
    news_module._cache.clear()


def test_context_calendar_route(monkeypatch):
    from app.context import calendar as calendar_module

    class FakeResp:
        def raise_for_status(self) -> None:
            return None

        def json(self):
            return []

    monkeypatch.setattr(calendar_module.httpx, "get", lambda *a, **k: FakeResp())
    calendar_module._cache = None

    resp = client.get("/api/engine/context/calendar")
    assert resp.status_code == 200
    assert resp.json() == {"events": []}
    calendar_module._cache = None


def test_agent_batch_is_order_stable_and_isolates_failures(monkeypatch):
    candles = _uptrend_with_spike(160)
    monkeypatch.setattr(binance, "fetch_klines", lambda symbol, tf, limit: candles)

    resp = client.post(
        "/api/engine/agent/batch",
        json={
            "commands": [
                {"cmd": "detect_signal", "args": {"symbol": "BTCUSDT"}},
                {"cmd": "unknown_cmd", "args": {}},
                {"cmd": "detect_signal", "args": {"symbol": "ETHUSDT"}},
            ]
        },
    )
    results = resp.json()["results"]
    assert len(results) == 3
    assert results[0]["ok"] is True and results[0]["data"]["symbol"] == "BTCUSDT"
    assert results[1]["ok"] is False
    assert results[2]["ok"] is True and results[2]["data"]["symbol"] == "ETHUSDT"


def test_agent_batch_rejects_more_than_20_commands():
    resp = client.post(
        "/api/engine/agent/batch",
        json={"commands": [{"cmd": "list_tools", "args": {}} for _ in range(21)]},
    )
    assert resp.status_code == 422
    assert "batch_too_large" in resp.json()["detail"]


def test_agent_batch_empty_returns_empty_results():
    resp = client.post("/api/engine/agent/batch", json={"commands": []})
    assert resp.status_code == 200
    assert resp.json() == {"results": []}
