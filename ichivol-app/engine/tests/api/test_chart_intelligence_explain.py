"""AW1 — « Pourquoi ? » : explain_chart_object (engine truth, no invented values)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.chart_intelligence import service as svc
from app.chart_intelligence.explain import ExplainError, explain_from_pack
from app.main import app
from tests.api.test_chart_intelligence_route import _candles, _fvg_series, _patch_fetch

client = TestClient(app)


def _clear_cache() -> None:
    with svc._REPLAY_CACHE_LOCK:
        svc._REPLAY_CACHE.clear()


def _pack(monkeypatch, candles, *, lookback: int = 24, limit: int = 300):
    _patch_fetch(monkeypatch, candles)
    now = candles[-1].time + 3600 + 10
    monkeypatch.setattr("app.chart_intelligence.service.time.time", lambda: now)
    _clear_cache()
    return svc.build_chart_intelligence_replay(
        symbol="BTCUSDT",
        timeframe="1h",
        limit=limit,
        lookback_bars=lookback,
        sources="engine",
        now=now,
    )


def _resolve(obj: dict, field: str):
    cur = obj
    for part in field.split("."):
        cur = cur[part]
    return cur


def test_every_fact_is_read_from_the_object(monkeypatch):
    """Aucune valeur inventée : chaque fait == le champ Python qu'il cite."""
    pack = _pack(monkeypatch, _candles(260))
    engine_objs = [o for o in pack["objects"] if o.get("source") == "engine"]
    assert engine_objs
    kinds = set()
    for o in engine_objs:
        ex = explain_from_pack(pack, object_id=o["id"])
        kinds.add(ex["identity"]["kind"])
        assert ex["object_id"] == o["id"]
        assert ex["validation"]["status"] == "NON_VALIDE"
        for f in ex["facts"]:
            raw = _resolve(ex["object"], f["field"])
            if isinstance(raw, float):
                assert f["value"] == pytest.approx(raw, abs=1e-6)
            else:
                assert f["value"] == raw
    assert {"structure_zone", "fvg", "fibonacci"} <= kinds


def test_fvg_known_at_lag_and_maturity(monkeypatch):
    candles = _fvg_series(8)
    pack = _pack(monkeypatch, candles, lookback=10, limit=80)
    fvg = next(
        o
        for o in pack["objects"]
        if (o.get("origin") or {}).get("kind") == "fvg" and float(o.get("price_low") or 0) == 100.0
    )
    ex = explain_from_pack(pack, lineage_key=fvg["origin"]["lineage_key"])
    tl = ex["timeline"]
    assert tl["known_at"] == int(candles[2].time)
    assert tl["known_at_is_upper_bound"] is False
    # Ancre = 1re bougie du motif (bar 0) ; détecté à la bar 2 → 2 barres de délai.
    assert tl["anchor_time"] == int(candles[0].time)
    assert tl["detection_lag_bars"] == 2
    assert ex["identity"]["maturity"]["status"] == "EXPERIMENTAL"
    assert ex["identity"]["maturity"]["feature"] == "fvg"
    assert "Non lu par le pipeline" in ex["identity"]["pipeline"]
    assert any("EXPERIMENTAL" in c for c in ex["caveats"])
    assert tl["status_history"] and tl["status_history"][0]["status"] == "open"
    assert ex["context"]["position"] == "above"


def test_known_at_upper_bound_when_present_at_window_start(monkeypatch):
    pack = _pack(monkeypatch, _candles(260))
    first = pack["from"]
    old = [o for o in pack["objects"] if (o.get("origin") or {}).get("known_at") == first]
    assert old, "fixture should contain objects already present at window start"
    ex = explain_from_pack(pack, object_id=old[0]["id"])
    assert ex["timeline"]["known_at_is_upper_bound"] is True
    assert ex["timeline"]["detection_lag_bars"] is None
    assert any("antérieure" in c for c in ex["caveats"])


def test_frame_id_resolves_through_lineage(monkeypatch):
    """Un id vu dans une frame ancienne retrouve l'objet final via lineage_key."""
    pack = _pack(monkeypatch, _candles(260))
    final_ids = {o["id"] for o in pack["objects"]}
    for frame in pack["frames"]:
        for o in frame["objects"]:
            lk = (o.get("origin") or {}).get("lineage_key")
            if o["id"] not in final_ids and lk and any(
                (f.get("origin") or {}).get("lineage_key") == lk for f in pack["objects"]
            ):
                ex = explain_from_pack(pack, object_id=o["id"])
                assert ex["lineage_key"] == lk
                return
    pytest.skip("no id churn in fixture")


def test_not_found_and_missing_args(monkeypatch):
    pack = _pack(monkeypatch, _candles(200))
    with pytest.raises(ExplainError):
        explain_from_pack(pack, object_id="does-not-exist")
    with pytest.raises(ExplainError):
        explain_from_pack(pack)


def test_http_explain_route(monkeypatch):
    candles = _candles(260)
    pack = _pack(monkeypatch, candles)
    oid = next(o["id"] for o in pack["objects"] if o["layer"] == "fibonacci")
    r = client.get(
        "/api/engine/chart-intelligence/BTCUSDT/explain",
        params={"timeframe": "1h", "object_id": oid, "lookback_bars": 24},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["identity"]["layer"] == "fibonacci"
    assert body["identity"]["maturity"]["feature"] == "impulse"

    r404 = client.get(
        "/api/engine/chart-intelligence/BTCUSDT/explain",
        params={"timeframe": "1h", "object_id": "nope", "lookback_bars": 24},
    )
    assert r404.status_code == 404
    r422 = client.get("/api/engine/chart-intelligence/BTCUSDT/explain", params={"timeframe": "1h"})
    assert r422.status_code == 422


def test_agent_command_registered_read_only(monkeypatch):
    from app.agent_channel.registry import list_tool_specs

    spec = next(t for t in list_tool_specs() if t["name"] == "explain_chart_object")
    assert spec["read_only"] is True

    candles = _candles(260)
    pack = _pack(monkeypatch, candles)
    oid = next(o["id"] for o in pack["objects"] if o["layer"] == "structure")
    r = client.post(
        "/api/engine/agent/command",
        json={"cmd": "explain_chart_object", "args": {"symbol": "BTCUSDT", "object_id": oid, "lookback_bars": 24}},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True
    assert body["data"]["object_id"] == oid
