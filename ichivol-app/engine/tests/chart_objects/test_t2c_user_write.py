"""T2c — USER HTTP write/delete for ENTRY/STOP/TARGET chart objects."""

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


def _patch_fetch(monkeypatch, candles: list[Candle]) -> None:
    def fake_resolve(symbol, timeframe, limit):
        class P:
            id = "test"

        return P(), symbol, candles[:limit]

    monkeypatch.setattr(
        "app.chart_objects.user_write.resolve_and_fetch", fake_resolve
    )
    monkeypatch.setattr(
        "app.chart_objects.collect.resolve_and_fetch", fake_resolve
    )


def test_post_user_entry_stop_target_with_setup_id(monkeypatch):
    candles = _candles()
    _patch_fetch(monkeypatch, candles)
    setup = "setup-test-abc"
    c = candles[50]

    for typ, label in (("entry", "Entry"), ("stop", "Stop"), ("target", "Target")):
        price = c.close if typ == "entry" else (c.low if typ == "stop" else c.high)
        resp = client.post(
            "/api/engine/chart-objects/T2CUSDT",
            json={
                "type": typ,
                "timeframe": "1h",
                "price": price,
                "time": c.time,
                "side": "LONG",
                "label": label,
                "setup_id": setup,
            },
        )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["upserted"] is True
        obj = body["object"]
        assert obj["source"] == "user"
        assert obj["type"] == typ
        assert obj["origin"]["setup_id"] == setup
        assert obj["subtype"] == f"setup:{setup}"
        assert obj["origin"]["via"] == "user_mark_trade"

    listed = client.get(
        "/api/engine/chart-objects/T2CUSDT?timeframe=1h&sources=user&limit=120"
    )
    assert listed.status_code == 200
    objs = listed.json()["objects"]
    assert len(objs) >= 3
    by_type = {o["type"]: o for o in objs if o.get("origin", {}).get("setup_id") == setup}
    assert set(by_type) == {"entry", "stop", "target"}


def test_post_rejects_non_trade_type(monkeypatch):
    candles = _candles()
    _patch_fetch(monkeypatch, candles)
    c = candles[10]
    resp = client.post(
        "/api/engine/chart-objects/T2CUSDT",
        json={
            "type": "zone",
            "timeframe": "1h",
            "price_low": 90,
            "price_high": 110,
            "time": c.time,
        },
    )
    assert resp.status_code == 422
    assert "entry|stop|target" in resp.json()["detail"]


def test_post_rejects_ungrounded_price(monkeypatch):
    candles = _candles()
    _patch_fetch(monkeypatch, candles)
    c = candles[10]
    resp = client.post(
        "/api/engine/chart-objects/T2CUSDT",
        json={
            "type": "entry",
            "timeframe": "1h",
            "price": c.close * 100,
            "time": c.time,
            "setup_id": "bad-price",
        },
    )
    assert resp.status_code == 422
    assert "point_not_grounded" in resp.json()["detail"]


def test_delete_user_only_leaves_claude(monkeypatch):
    candles = _candles()
    _patch_fetch(monkeypatch, candles)
    monkeypatch.setattr(
        "app.agent_channel.commands.resolve_and_fetch",
        lambda symbol, timeframe, limit: (
            type("P", (), {"id": "test"})(),
            symbol,
            candles[:limit],
        ),
    )
    c = candles[20]

    user = client.post(
        "/api/engine/chart-objects/T2CUSDT",
        json={
            "type": "entry",
            "timeframe": "1h",
            "price": c.close,
            "time": c.time,
            "setup_id": "del-user",
            "side": "LONG",
        },
    )
    assert user.status_code == 200
    uid = user.json()["object"]["id"]

    claude = client.post(
        "/api/engine/agent/command",
        json={
            "cmd": "draw_entry",
            "args": {
                "symbol": "T2CUSDT",
                "timeframe": "1h",
                "price": candles[21].close,
                "time": candles[21].time,
                "side": "LONG",
                "label": "agent",
            },
        },
    )
    assert claude.json()["ok"] is True
    cid = claude.json()["data"]["object"]["id"]

    # Cannot delete CLAUDE via USER delete route.
    bad = client.delete(f"/api/engine/chart-objects/item/{cid}")
    assert bad.status_code == 404

    ok = client.delete(f"/api/engine/chart-objects/item/{uid}")
    assert ok.status_code == 200
    assert ok.json()["deleted"] is True
    assert ok.json()["source"] == "user"

    listed = client.get(
        "/api/engine/chart-objects/T2CUSDT?timeframe=1h&sources=user,claude&limit=120"
    )
    ids = {o["id"] for o in listed.json()["objects"]}
    assert uid not in ids
    assert cid in ids


def test_post_forces_source_user(monkeypatch):
    candles = _candles()
    _patch_fetch(monkeypatch, candles)
    c = candles[5]
    resp = client.post(
        "/api/engine/chart-objects/T2CUSDT",
        json={
            "type": "stop",
            "timeframe": "1h",
            "price": c.low,
            "time": c.time,
            "source": "claude",
            "setup_id": "force-user",
        },
    )
    assert resp.status_code == 200
    assert resp.json()["object"]["source"] == "user"
