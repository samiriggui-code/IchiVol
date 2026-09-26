"""API smoke + CI-R1/R2/R7/R8/R9 for Chart Intelligence."""

from __future__ import annotations

import json
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


def _fvg_series(n_after: int = 12) -> list[Candle]:
    """Bullish FVG that stays open for ``n_after`` bars (CI-R8)."""
    # Discovery at bar 2 (gap [100, 110]); then drift above gap.
    ohlc: list[tuple[float, float, float, float]] = [
        (99, 100, 98, 99),
        (99, 108, 99, 107),
        (107, 112, 110, 111),
    ]
    price = 111.0
    for _ in range(n_after):
        ohlc.append((price, price + 1.0, price - 0.3, price + 0.5))
        price += 0.5
    return [
        Candle(
            time=1_700_000_000 + i * 3600,
            open=o,
            high=h,
            low=lo,
            close=c,
            volume=100.0,
        )
        for i, (o, h, lo, c) in enumerate(ohlc)
    ]


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
    """CI-R1: for 3 values of T, frame objects == build_chart_intelligence(as_of=T).

    CI-R7: frames omit candles/ichimoku/projection; pack size < 1.5 Mo for
    lookback=48 on 300-bar window.
    """
    candles = _candles(360)
    _patch_fetch(monkeypatch, candles)
    monkeypatch.setattr(
        "app.chart_intelligence.service.time.time",
        lambda: candles[-1].time + 3600 + 10,
    )
    from app.chart_intelligence import service as svc

    with svc._REPLAY_CACHE_LOCK:
        svc._REPLAY_CACHE.clear()

    lookback = 48
    resp = client.get(
        "/api/engine/chart-intelligence/BTCUSDT/replay"
        f"?timeframe=1h&limit=300&lookback_bars={lookback}&sources=engine"
    )
    assert resp.status_code == 200, resp.text
    pack = resp.json()
    assert pack["replay_mode"] == "walk_forward"
    frames = pack["frames"]
    assert len(frames) == lookback
    # CI-R7: series once at root; frames are slim.
    assert "candles" in pack and len(pack["candles"]) == 300
    assert "ichimoku" in pack
    assert "projection" in pack
    for frame in frames:
        assert set(frame.keys()) == {"as_of", "objects", "market_state"}
        assert "candles" not in frame
        assert "ichimoku" not in frame
        assert "projection" not in frame

    raw = json.dumps(pack).encode("utf-8")
    assert len(raw) < int(1.5 * 1024 * 1024), f"pack too large: {len(raw)} bytes"

    sample_idx = [0, lookback // 2, lookback - 1]
    for idx in sample_idx:
        frame = frames[idx]
        t = frame["as_of"]
        live = svc.build_chart_intelligence(
            symbol="BTCUSDT",
            timeframe="1h",
            limit=300,
            as_of=t,
            sources="engine",
            now=candles[-1].time + 3600 + 10,
        )
        live_cores = sorted(_obj_core(o) for o in live["objects"])
        frame_cores = sorted(_obj_core(o) for o in frame["objects"])
        assert frame_cores == live_cores, f"mismatch at T={t} idx={idx}"
        for o in frame["objects"]:
            ka = (o.get("origin") or {}).get("known_at")
            if ka is not None:
                assert int(ka) <= int(t)


def test_ci_r8_fvg_lineage_stable_known_at(monkeypatch):
    """CI-R8: a living FVG keeps the same lineage_key; known_at = detection bar."""
    # 3 discovery bars + 8 after → lookback=10 includes detection (idx 2).
    candles = _fvg_series(8)
    _patch_fetch(monkeypatch, candles)
    monkeypatch.setattr(
        "app.chart_intelligence.service.time.time",
        lambda: candles[-1].time + 3600 + 10,
    )
    from app.chart_intelligence import service as svc
    from app.chart_objects.from_fvg import fvg_to_chart_objects
    from app.indicators.fvg import FvgParams

    with svc._REPLAY_CACHE_LOCK:
        svc._REPLAY_CACHE.clear()

    detect_t = int(candles[2].time)
    pack = svc.build_chart_intelligence_replay(
        symbol="BTCUSDT",
        timeframe="1h",
        limit=80,
        lookback_bars=10,
        sources="engine",
        now=candles[-1].time + 3600 + 10,
    )
    keys: list[str] = []
    knowns: list[int] = []
    for frame in pack["frames"]:
        fvgs = [
            o
            for o in frame["objects"]
            if (o.get("origin") or {}).get("kind") == "fvg"
            and (o.get("origin") or {}).get("direction") == "bullish"
            and float(o.get("price_low") or 0) == 100.0
        ]
        if int(frame["as_of"]) < detect_t:
            assert not fvgs, "FVG must not appear before detection bar"
            continue
        assert fvgs, f"expected FVG at as_of={frame['as_of']}"
        origin = fvgs[0].get("origin") or {}
        assert origin.get("lineage_key")
        keys.append(str(origin["lineage_key"]))
        knowns.append(int(origin["known_at"]))

    assert keys, "expected FVG frames after detection"
    assert len(set(keys)) == 1, f"lineage_key drifted: {set(keys)}"
    assert all(k == knowns[0] for k in knowns)
    assert knowns[0] == detect_t

    objs = fvg_to_chart_objects(candles, "BTCUSDT", "1h", params=FvgParams(min_gap_atr=0.0))
    bull = [o for o in objs if o.origin.get("direction") == "bullish" and o.price_low == 100.0]
    assert bull
    assert bull[0].origin["lineage_key"] == keys[0]


def test_ci_r9_replay_cache_lru_and_purge(monkeypatch):
    """CI-R9: cache capped at 32; expired entries purged on write."""
    candles = _candles(120)
    _patch_fetch(monkeypatch, candles)
    monkeypatch.setattr(
        "app.chart_intelligence.service.time.time",
        lambda: candles[-1].time + 3600 + 10,
    )
    from app.chart_intelligence import service as svc

    with svc._REPLAY_CACHE_LOCK:
        svc._REPLAY_CACHE.clear()

    # Fill beyond max with distinct lookbacks (same series end → distinct keys).
    for i in range(svc._REPLAY_CACHE_MAX + 5):
        lb = 2 + (i % 50)
        svc.build_chart_intelligence_replay(
            symbol="BTCUSDT",
            timeframe="1h",
            limit=60,
            lookback_bars=lb,
            from_ts=candles[-(lb + i % 3) - 5].time if i % 3 else None,
            to_ts=candles[-1].time - (i % 4) * 3600,
            sources="engine",
            now=candles[-1].time + 3600 + 10,
        )

    with svc._REPLAY_CACHE_LOCK:
        assert len(svc._REPLAY_CACHE) <= svc._REPLAY_CACHE_MAX

    # Expired purge on write: plant a stale entry, then write a fresh one.
    stale_key = ("STALE", "1h", 0, 0, 0, 2)
    with svc._REPLAY_CACHE_LOCK:
        svc._REPLAY_CACHE[stale_key] = (0.0, {"cached": False})  # already expired
        assert stale_key in svc._REPLAY_CACHE

    svc.build_chart_intelligence_replay(
        symbol="ETHUSDT",
        timeframe="1h",
        limit=40,
        lookback_bars=4,
        sources="engine",
        now=candles[-1].time + 3600 + 10,
    )
    with svc._REPLAY_CACHE_LOCK:
        assert stale_key not in svc._REPLAY_CACHE
        assert len(svc._REPLAY_CACHE) <= svc._REPLAY_CACHE_MAX
