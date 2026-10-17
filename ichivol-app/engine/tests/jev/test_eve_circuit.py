"""Ève Intelligence V1 — JEV client contract, the circuit (Ève decides, else the engine), Dossier IchiVol."""

from __future__ import annotations

from types import SimpleNamespace

import httpx
import pytest
from sqlalchemy import delete
from sqlalchemy.exc import OperationalError

from app.agents.types import Direction
from app.db.models import EveDossier
from app.db.session import SessionLocal, engine
from app.decision.pipeline import PipelineResult
from app.jev import client as jev_client
from app.jev import dossier as eve_dossier
from app.jev.client import JevCall, JevEndpoint, system_one
from app.jev.questions import entry_battery, manage_battery
from app.jev.state import MAX_STATE_CHARS, build_state, state_chars
from app.jev.verdict import decide_entry, decide_manage, engine_action, execute, pipeline_decision_for
from app.paper import engine as paper

try:
    with engine.connect():
        pass
    DB_AVAILABLE = True
except OperationalError:
    DB_AVAILABLE = False

SYMBOL = "EVETEST"


def _entry_answers(choice="long", p=0.7, conf=0.6, quality=3.0, contradiction=0.2):
    probs = {"long": p, "abstain": 1 - p} if choice != "short" else {"short": p, "long": 0.0, "abstain": 1 - p}
    return {
        "decision": {"type": "choice", "choice": choice, "probabilities": probs, "confidence": conf},
        "regime": {"type": "choice", "choice": "trend", "probabilities": {"trend": 0.8}, "confidence": 0.5},
        "quality": {"type": "score", "score": quality, "probabilities": {"3": 1.0}, "confidence": 0.5},
        "contradiction": {"type": "noul", "noul": contradiction},
        "engine_supported": {"type": "noul", "noul": 0.6},
    }


# ---- client -------------------------------------------------------------------------------------------------


def _ep(name, url, key="k"):
    return JevEndpoint(name, url, key, "jev-latest", 2.0)


def test_client_validates_and_falls_back_when_primary_refuses():
    qs = entry_battery(allow_short=False)
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append((request.url.host, request.headers.get("authorization")))
        if request.url.host == "api.typesafe.ai":
            return httpx.Response(402, json={"error": "insufficient credits"})
        return httpx.Response(200, json={"model": "jevos-v4", "answers": _entry_answers(), "usage": {"input_tokens": 9}})

    with httpx.Client(transport=httpx.MockTransport(handler)) as c:
        call = system_one({"x": 1}, qs, endpoints=[_ep("primary", "https://api.typesafe.ai"),
                                                    _ep("fallback", "http://jevos-v4:8017", "")], client=c)
    assert call.ok and call.provider == "jevos" and call.errors == ["typesafe:http_402"]
    assert seen[0] == ("api.typesafe.ai", "Bearer k") and seen[1][1] is None
    assert call.answers["decision"]["choice"] == "long"


def test_client_rejects_answers_outside_the_contract():
    qs = entry_battery(allow_short=False)
    bad = _entry_answers()
    bad["decision"]["choice"] = "short"  # not offered on a long-only portfolio
    bad["contradiction"]["noul"] = 1.4

    with httpx.Client(transport=httpx.MockTransport(lambda r: httpx.Response(200, json={"answers": bad}))) as c:
        call = system_one({}, qs, endpoints=[_ep("primary", "http://jevos-v4:8017")], client=c)
    assert not call.ok and call.error == "invalid_answers"
    assert "decision:choice" in call.errors and "contradiction:noul" in call.errors


def test_hosted_primary_without_key_is_skipped(monkeypatch):
    monkeypatch.delenv("JEV_API_KEY", raising=False)
    monkeypatch.delenv("JEV_URL", raising=False)
    monkeypatch.delenv("JEV_FALLBACK_URL", raising=False)
    eps = jev_client.endpoints_from_env()
    assert [e.label for e in eps] == ["jevos"]
    monkeypatch.setenv("JEV_API_KEY", "secret")
    assert [e.label for e in jev_client.endpoints_from_env()] == ["typesafe", "jevos"]


# ---- verdict & circuit -----------------------------------------------------------------------------------------


def test_eve_decides_and_never_hands_over_to_the_engine():
    v = decide_entry(_entry_answers(), engine_decision="NO_TRADE")
    assert execute(v, holding=None) == ("LONG", "eve")

    weak = decide_entry(_entry_answers(p=0.51), engine_decision="BUY")
    assert not weak.decisive
    assert execute(weak, holding=None) == ("ABSTAIN", "eve_indecise")

    down = decide_entry(None, engine_decision="BUY")
    assert execute(down, holding=None) == ("ABSTAIN", "eve_indecise")

    # An explicit abstention is a decision.
    ab = decide_entry(_entry_answers(choice="abstain", p=0.2), engine_decision="BUY")
    assert execute(ab, holding=None) == ("ABSTAIN", "eve")

    veto = decide_entry(_entry_answers(contradiction=0.95), engine_decision="BUY")
    assert execute(veto, holding=None) == ("ABSTAIN", "eve_indecise")


def test_manage_close_and_hold():
    close = {"manage": {"type": "choice", "choice": "close", "probabilities": {"close": 0.8, "hold": 0.2},
                        "confidence": 0.7}}
    v = decide_manage(close, holding="LONG", engine_decision="BUY")
    assert execute(v, holding="LONG") == ("CLOSE", "eve")
    assert pipeline_decision_for("CLOSE", "LONG") == "NO_TRADE"
    assert pipeline_decision_for("HOLD", "SHORT") == "SELL"
    down = decide_manage(None, holding="LONG", engine_decision="WATCH")
    assert execute(down, holding="LONG") == ("HOLD", "eve_indecise")
    assert engine_action("WATCH", "LONG") == "CLOSE"


def test_jevos_account_only_calls_jevos(monkeypatch):
    monkeypatch.setenv("JEV_API_KEY", "secret")
    monkeypatch.delenv("JEV_URL", raising=False)
    monkeypatch.delenv("JEV_FALLBACK_URL", raising=False)
    assert [e.label for e in jev_client.endpoints_for("jev")] == ["typesafe", "jevos"]
    assert [e.label for e in jev_client.endpoints_for("jevos")] == ["jevos"]


def test_state_is_bounded_and_keeps_the_pipeline():
    detail = {"symbol": "X", "timeframe": "1h", "price": 1.0, "pipeline": {"decision": "BUY"},
              "evidence": {"blob": ["y" * 390] * 12}, "context": {"blob": ["z" * 390] * 12},
              "lab_context": {"a": ["q" * 390] * 12}, "mtf_matrix": {"b": ["w" * 390] * 12},
              "data_provenance": {"secret": "dropped"}}
    for i in range(3):
        detail[f"extra{i}"] = ["v" * 390] * 12
    st = build_state(detail, position=None, allow_short=False, portfolio_code="P")
    assert state_chars(st) <= MAX_STATE_CHARS  # trims optional blocks first
    assert st["engine"]["pipeline"] == {"decision": "BUY"} and "data_provenance" not in st["engine"]
    assert st["omitted_for_size"]


# ---- Dossier IchiVol in the paper loop (Postgres) --------------------------------------------------------------

needs_db = pytest.mark.skipif(not DB_AVAILABLE, reason="ichivol_engine_dev Postgres not reachable")


@pytest.fixture
def db():
    s = SessionLocal()
    s.execute(delete(EveDossier).where(EveDossier.symbol.like(f"{SYMBOL}%")))
    s.commit()
    yield s
    s.rollback()
    s.execute(delete(EveDossier).where(EveDossier.symbol.like(f"{SYMBOL}%")))
    s.commit()
    s.close()


def _row(decision="NO_TRADE", bar_close=1_800_000_000, symbol=SYMBOL):
    return SimpleNamespace(
        symbol=symbol, timeframe="1h", price=100.0,
        pipeline=PipelineResult(decision=decision, direction=Direction.LONG, stages=[]),
        atr=SimpleNamespace(suggested_stop_distance=2.0), candles=[], rvol=None, mtf_matrix=None,
        signal_timing={"signal_bar_close": bar_close},
    )


def _fake_jev(monkeypatch, answers):
    calls = []

    def fake(state, questions, **kw):
        calls.append([e.label for e in kw.get("endpoints") or []])
        if answers is None:
            return JevCall(ok=False, error="jev_unavailable", errors=["typesafe:http_402", "jevos:ConnectError"])
        return JevCall(ok=True, answers=answers, model="jev-latest", provider="typesafe", usage={"input_tokens": 1})

    monkeypatch.setattr(eve_dossier.jev_client, "system_one", fake)
    return calls


ACCOUNTS = (("BASE", None), ("EVE_A", "jev"), ("EVE_B", "jev"), ("EVE_L", "jevos"))


def _loop(monkeypatch, db, rows, accounts=ACCOUNTS):
    monkeypatch.setenv("EVE_ENABLED", "true")
    monkeypatch.setenv("JEV_API_KEY", "secret")
    seen: list[dict] = []
    monkeypatch.setattr(paper, "sync_position", lambda session, **kw: seen.append(kw))
    monkeypatch.setattr(paper, "ensure_syncable_portfolios", lambda session: [
        SimpleNamespace(id=f"00000000-0000-0000-0000-00000000000{i}", code=c,
                        strategy_profile={"auto_timeframes": ["1h"], "allow_short": False,
                                          **({"eve_source": src} if src else {})})
        for i, (c, src) in enumerate(accounts)
    ])
    monkeypatch.setattr(paper.shadow_broker, "mark_shadows", lambda *a, **k: None)
    monkeypatch.setattr(paper.paper_broker, "snapshot_equity", lambda *a, **k: None)
    paper.sync_auto_watchlist(db, rows)
    return {kw["signal_extra"]["portfolio_code"]: kw for kw in seen}


def _dossiers(db):
    return {d.portfolio_code: d for d in db.query(EveDossier).filter(EveDossier.symbol == SYMBOL)}


@needs_db
def test_eve_accounts_trade_on_eve_decision_and_the_baseline_is_untouched(monkeypatch, db):
    calls = _fake_jev(monkeypatch, _entry_answers())
    seen = _loop(monkeypatch, db, [_row("NO_TRADE")])
    # Baseline: engine signal, no Ève. Ève accounts: Ève decided LONG though the engine said NO_TRADE.
    assert seen["BASE"]["pipeline"].decision == "NO_TRADE" and "eve" not in seen["BASE"]["signal_extra"]
    for code in ("EVE_A", "EVE_B", "EVE_L"):
        assert seen[code]["pipeline"].decision == "BUY" and seen[code]["signal_actions"] is True
    # One hosted call shared by the two hosted accounts, one jevos-only call.
    assert sorted(calls) == [["jevos"], ["typesafe", "jevos"]]
    ds = _dossiers(db)
    assert set(ds) == {"EVE_A", "EVE_B", "EVE_L"}
    assert (ds["EVE_A"].decided_by, ds["EVE_A"].executed_action, ds["EVE_A"].engine_action) == ("eve", "LONG", "ABSTAIN")
    assert ds["EVE_A"].reused is False and ds["EVE_B"].reused is True and ds["EVE_B"].state is None

    # Next 300 s cycle on the same closed bar: no new call, same decision.
    seen2 = _loop(monkeypatch, db, [_row("NO_TRADE")])
    assert len(calls) == 2 and seen2["EVE_A"]["pipeline"].decision == "BUY"


@needs_db
def test_jev_down_eve_abstains_and_the_engine_does_not_take_over(monkeypatch, db):
    _fake_jev(monkeypatch, None)
    seen = _loop(monkeypatch, db, [_row("BUY")], accounts=(("EVE_A", "jev"),))
    assert seen["EVE_A"]["pipeline"].decision == "NO_TRADE"
    d = _dossiers(db)["EVE_A"]
    assert (d.decided_by, d.eve_action, d.executed_action, d.engine_action, d.jev_error) == (
        "eve_indecise", "UNAVAILABLE", "ABSTAIN", "LONG", "jev_unavailable")


@needs_db
def test_daily_cap_only_limits_the_hosted_account(monkeypatch, db):
    calls = _fake_jev(monkeypatch, _entry_answers())
    monkeypatch.setenv("JEV_DAILY_MAX_CALLS", "0")
    seen = _loop(monkeypatch, db, [_row("WATCH")], accounts=(("EVE_A", "jev"), ("EVE_L", "jevos")))
    assert calls == [["jevos"]]
    assert seen["EVE_A"]["pipeline"].decision == "NO_TRADE" and seen["EVE_L"]["pipeline"].decision == "BUY"
    assert _dossiers(db)["EVE_A"].jev_error == "daily_cap"


@needs_db
def test_observation_mode_records_without_acting(monkeypatch, db):
    _fake_jev(monkeypatch, _entry_answers())
    monkeypatch.setenv("EVE_EXECUTION", "false")
    seen = _loop(monkeypatch, db, [_row("NO_TRADE")], accounts=(("EVE_A", "jev"),))
    assert seen["EVE_A"]["signal_actions"] is False
    d = _dossiers(db)["EVE_A"]
    assert (d.eve_action, d.decided_by) == ("LONG", "observation")


@needs_db
def test_eve_account_without_eve_never_follows_the_engine(monkeypatch, db):
    calls = _fake_jev(monkeypatch, _entry_answers())
    seen = _loop(monkeypatch, db, [_row("BUY", bar_close=None)], accounts=(("EVE_A", "jev"),))
    assert calls == [] and seen["EVE_A"]["signal_actions"] is False


@needs_db
def test_outcome_and_calibration(monkeypatch, db):
    _fake_jev(monkeypatch, _entry_answers())
    bar = 1_800_000_000
    _loop(monkeypatch, db, [_row("NO_TRADE", bar_close=bar)], accounts=(("EVE_A", "jev"),))
    candles = [SimpleNamespace(time=bar - 3600 + i * 3600, close=100.0 + i) for i in range(6)]
    assert eve_dossier.fill_outcomes(db, {f"{SYMBOL}:1h": candles}) == 1
    d = _dossiers(db)["EVE_A"]
    assert d.outcome_return == pytest.approx(0.04)  # close 100 -> 104 four bars later
    cal = eve_dossier.calibration(db, portfolio_code="EVE_A")
    assert cal["calibration"]["n"] == 1 and cal["calibration"]["brier"] == pytest.approx(0.09)
    assert cal["comparison"]["eve_when_decisive"]["mean"] == pytest.approx(0.04)
    assert cal["comparison"]["engine_alone"]["mean"] == 0.0
    assert cal["decided_by"]["eve"] == 1


@needs_db
def test_eve_api_status_list_detail_calibration(monkeypatch, db):
    from fastapi.testclient import TestClient

    from app.main import app

    _fake_jev(monkeypatch, _entry_answers())
    _loop(monkeypatch, db, [_row("NO_TRADE")], accounts=(("EVE_A", "jev"), ("EVE_B", "jev")))
    c = TestClient(app)
    st = c.get("/api/engine/eve/status").json()
    assert [p["code"] for p in st["portfolios"]] == ["EVE_JEV_V1", "EVE_JEVOS_V1"]
    assert all("api_key" not in e and "url" not in e for e in st["endpoints"])  # never leaks a secret
    rows = c.get("/api/engine/eve/dossiers", params={"symbol": SYMBOL}).json()["results"]
    assert {r["portfolio_code"] for r in rows} == {"EVE_A", "EVE_B"}
    reused = next(r for r in rows if r["portfolio_code"] == "EVE_B")
    det = c.get(f"/api/engine/eve/dossiers/{reused['id']}").json()
    assert det["state"]["engine"] and det["call_source_id"] and det["labels_fr"]["decision"]
    assert c.get("/api/engine/eve/dossiers/nope").status_code == 404
    assert c.get("/api/engine/eve/calibration", params={"portfolio": "EVE_A"}).status_code == 200


@needs_db
def test_eve_account_opens_then_liquidates_through_the_real_broker(monkeypatch, db):
    """End to end on a throwaway Ève account: Ève buys though the engine says NO_TRADE, then liquidates though
    the engine still says BUY (the baseline's direction exit must not bypass her)."""
    from tests.paper.test_engine import _disposable, _drop_portfolio

    from app.db.models import PaperPosition
    from app.paper.strategy_profiles import EVE_JEV_CODE, profile_for

    monkeypatch.setenv("EVE_ENABLED", "true")
    monkeypatch.setenv("JEV_API_KEY", "secret")
    pf = _disposable(db, **{k: v for k, v in profile_for(EVE_JEV_CODE).items() if k != "code"})
    db.commit()
    monkeypatch.setattr(paper, "ensure_syncable_portfolios", lambda session: [pf])
    sym = f"{SYMBOL}E2E"
    try:
        _fake_jev(monkeypatch, _entry_answers())
        paper.sync_auto_watchlist(db, [_row("NO_TRADE", bar_close=1_800_000_000, symbol=sym)])
        pos = db.query(PaperPosition).filter_by(portfolio_id=pf.id, symbol=sym).one()
        assert pos.status == "OPEN" and pos.direction == "LONG"
        d1 = db.query(EveDossier).filter_by(portfolio_code=pf.code, symbol=sym).one()
        assert (d1.executed_result, d1.position_id) == ("opened", pos.id)

        close = {
            "manage": {"type": "choice", "choice": "close", "probabilities": {"close": 0.9, "hold": 0.1},
                       "confidence": 0.8},
            "position_risk": {"type": "score", "score": 2.5, "probabilities": {"2": 1.0}, "confidence": 0.5},
            "thesis_valid": {"type": "noul", "noul": 0.1},
            "engine_supported": {"type": "noul", "noul": 0.3},
        }
        _fake_jev(monkeypatch, close)
        paper.sync_auto_watchlist(db, [_row("BUY", bar_close=1_800_003_600, symbol=sym)])
        db.refresh(pos)
        assert pos.status == "CLOSED" and pos.exit_reason == "eve_close"
        d2 = db.query(EveDossier).filter_by(portfolio_code=pf.code, symbol=sym, bar_time=1_800_003_600).one()
        assert (d2.battery, d2.executed_action, d2.engine_action) == ("manage", "CLOSE", "HOLD")
        assert d2.executed_result == "closed_eve_close"
    finally:
        db.query(EveDossier).filter(EveDossier.symbol == sym).delete()
        db.commit()
        _drop_portfolio(db, pf)
