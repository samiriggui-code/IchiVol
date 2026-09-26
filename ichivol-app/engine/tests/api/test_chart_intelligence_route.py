"""API smoke + CI-R1/R2 for Chart Intelligence."""

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


def _patch_fetch(monkeypatch, candles: list[Candle]):
    def fake_resolve(symbol, timeframe, limit):
        class P:
            id = "test"

        return P(), symbol, candles[:limit]

    monkeypatch.setattr(
        "app.chart_intelligence.service.resolve_and_fetch", fake_resolve
    )


def test_chart_intelligence_live_payload(monkeypatch):
    candles = _candles()
    _patch_fetch(monkeypatch, candles)
    # Force closed-candle path with now past last bar close.
    monkeypatch.setattr(
        "app.chart_intelligence.service.time.time",
        lambda: candles[-1].time + 3600 + 10,
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
    assert body["analysis"]["producer"] == "engine"
    assert body["analysis"]["kind"] == "pipeline"
    assert body["replay"]["bar_seconds"] == 3600
    assert body["replay"]["first"] <= body["as_of"]


def test_chart_intelligence_as_of_truncates(monkeypatch):
    candles = _candles()
    cut = candles[99].time
    _patch_fetch(monkeypatch, candles)
    monkeypatch.setattr(
        "app.chart_intelligence.service.time.time",
        lambda: candles[-1].time + 3600 + 10,
    )
    resp = client.get(
        f"/api/engine/chart-intelligence/BTCUSDT?timeframe=1h&limit=120&as_of={cut}&sources=engine"
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["as_of"] == cut
    assert all(c["time"] <= cut for c in body["candles"])
    assert body["replay"]["last"] == cut


def test_ci_r2_mid_bar_drops_forming_candle(monkeypatch):
    """CI-R2: mid-bar now must exclude the still-forming last candle."""
    candles = _candles(80)
    _patch_fetch(monkeypatch, candles)
    # Mid-bar: last candle opened but not closed yet.
    forming_open = candles[-1].time
    mid = forming_open + 1800  # +30 min on 1h

    from app.chart_intelligence.service import build_chart_intelligence

    body = build_chart_intelligence(
        symbol="BTCUSDT",
        timeframe="1h",
        limit=60,
        sources="engine",
        now=mid,
    )
    assert body["as_of"] < forming_open
    assert all(c["time"] < forming_open for c in body["candles"])
    assert body["as_of"] == candles[-2].time


def _obj_core(o: dict) -> tuple:
    origin = o.get("origin") or {}
    return (
        o.get("id"),
        origin.get("status"),
        o.get("price_low"),
        o.get("price_high"),
        o.get("confidence"),
    )


def test_ci_r1_replay_frames_match_as_of_builds(monkeypatch):
    """CI-R1: for 3 values of T, frame objects == build_chart_intelligence(as_of=T)."""
    candles = _candles(160)
    _patch_fetch(monkeypatch, candles)
    monkeypatch.setattr(
        "app.chart_intelligence.service.time.time",
        lambda: candles[-1].time + 3600 + 10,
    )
    # Clear replay cache between runs.
    from app.chart_intelligence import service as svc

    with svc._REPLAY_CACHE_LOCK:
        svc._REPLAY_CACHE.clear()

    lookback = 24
    resp = client.get(
        "/api/engine/chart-intelligence/BTCUSDT/replay"
        f"?timeframe=1h&limit=120&lookback_bars={lookback}&sources=engine"
    )
    assert resp.status_code == 200, resp.text
    pack = resp.json()
    assert pack["replay_mode"] == "walk_forward"
    frames = pack["frames"]
    assert len(frames) == lookback

    # Three sample T values across the walk.
    sample_idx = [0, lookback // 2, lookback - 1]
    for idx in sample_idx:
        frame = frames[idx]
        t = frame["as_of"]
        live = svc.build_chart_intelligence(
            symbol="BTCUSDT",
            timeframe="1h",
            limit=120,
            as_of=t,
            sources="engine",
            now=candles[-1].time + 3600 + 10,
        )
        live_cores = sorted(_obj_core(o) for o in live["objects"])
        frame_cores = sorted(_obj_core(o) for o in frame["objects"])
        assert frame_cores == live_cores, f"mismatch at T={t} idx={idx}"
        # known_at must be <= T (detection bar, not future)
        for o in frame["objects"]:
            ka = (o.get("origin") or {}).get("known_at")
            if ka is not None:
                assert int(ka) <= int(t)
