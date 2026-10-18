"""Ève autopilot — the engine proposes per book, once per closed bar. Ève disagrees → the engine trades anyway;
Ève agrees → the independent audit rules."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

from app.eve.autopilot import EveAutopilot, eve_accepts


def _prop(**kw: Any) -> dict[str, Any]:
    base = {"symbol": "BTCUSDT", "timeframe": "1h", "portfolio_code": "BASE", "price": 100.0,
            "stop_distance": 2.0, "engine_decision": "BUY", "signal_bar_close": 1_800_000_000}
    return base | kw


def test_eve_accepts_only_her_own_direction() -> None:
    open_long = _prop(action="OPEN", direction="LONG")
    assert eve_accepts(open_long, "LONG") is True
    assert eve_accepts(open_long, "SHORT") is False
    assert eve_accepts(open_long, "HOLD") is False
    assert eve_accepts(open_long, "ABSTAIN") is False
    assert eve_accepts(open_long, None) is False


def test_eve_close_needs_close_or_opposite_direction() -> None:
    close = _prop(action="CLOSE", position_id="p1")
    assert eve_accepts(close, "CLOSE", "LONG") is True
    assert eve_accepts(close, "SHORT", "LONG") is True
    assert eve_accepts(close, "LONG", "LONG") is False
    # Undecided keeps the lot.
    assert eve_accepts(close, "ABSTAIN", "LONG") is False
    assert eve_accepts(close, "HOLD", "LONG") is False


def _audit(*, choice: str | None = None, score: float | None = None, noul: float | None = None) -> dict[str, Any]:
    answers: dict[str, Any] = {}
    if choice is not None:
        answers["independent_action"] = {"type": "choice", "choice": choice}
    if score is not None:
        answers["audit_confidence"] = {"type": "score", "score": score}
    if noul is not None:
        answers["review"] = {"type": "noul", "noul": noul}
    return {"jev": {"ok": True, "answers": answers}} if answers else {}


def _pilot(
    eve_action: str, submitted: list[dict[str, Any]], audit: dict[str, Any] | None = None
) -> tuple[EveAutopilot, list[str]]:
    evaluated: list[str] = []

    def evaluate(symbol: str, timeframe: str, **kw: Any) -> dict[str, Any]:
        evaluated.append(symbol)
        assert kw["paper_dry_run"] is False  # the evaluation itself never trades
        return {"eve_action": eve_action, "dossier_id": f"d-{symbol}", "modes": {"shadow": audit or {}}}

    def submit(session: Any, dossier_id: str, **kw: Any) -> dict[str, Any]:
        submitted.append({"dossier_id": dossier_id, **kw})
        return {"status": "opened", "executed": True, "risk_authorization": "accepted", "position_id": "p-1"}

    return EveAutopilot(evaluate=evaluate, submit=submit), evaluated


def test_engine_trades_over_eve_and_her_agreement_goes_as_hers(monkeypatch: Any) -> None:
    monkeypatch.setenv("EVE_PAPER_AUTONOMY", "true")
    monkeypatch.setattr("app.eve.dossier.get_dossier", lambda s, i: None)
    submitted: list[dict[str, Any]] = []
    pilot, evaluated = _pilot("LONG", submitted)
    report = pilot.run_cycle(MagicMock(), [
        _prop(action="OPEN", direction="LONG", portfolio_code="BASE"),
        _prop(action="OPEN", direction="SHORT", portfolio_code="SESS", engine_decision="SELL"),
    ])
    assert evaluated == ["BTCUSDT"]  # one Ève evaluation per symbol, not per book
    by_book = {s["portfolio_code"]: s for s in submitted}
    # Agreement, no audit answer: Ève's trade.
    assert by_book["BASE"]["decided_by"] == "eve" and by_book["BASE"]["action_override"] is None
    # Ève wanted LONG, the engine SHORT: the engine trades its SHORT anyway.
    assert by_book["SESS"]["decided_by"] == "engine_over_eve" and by_book["SESS"]["action_override"] == "SHORT"
    outcomes = report["symbols"][0]["outcomes"]
    assert [(o["portfolio_code"], o["eve_accepts"], o["decided_by"], o["position_id"]) for o in outcomes] == [
        ("BASE", True, "eve", "p-1"), ("SESS", False, "engine_over_eve", "p-1"),
    ]
    assert outcomes[1]["eve_action"] == "LONG"  # Ève's answer is kept to score her


def test_audit_blocks_an_agreed_open(monkeypatch: Any) -> None:
    monkeypatch.setenv("EVE_PAPER_AUTONOMY", "true")
    monkeypatch.setattr("app.eve.dossier.get_dossier", lambda s, i: None)
    shadows: list[tuple[Any, ...]] = []
    submitted: list[dict[str, Any]] = []
    pilot, _ = _pilot("LONG", submitted, audit=_audit(choice="SHORT", score=3.0, noul=0.9))
    pilot._shadow = lambda *a: shadows.append(a[1:]) or "sh-1"
    report = pilot.run_cycle(MagicMock(), [_prop(action="OPEN", direction="LONG")])
    assert submitted == []
    out = report["symbols"][0]["outcomes"][0]
    assert out["status"] == "blocked_by_audit" and out["decided_by"] == "audit"
    assert out["audit"]["reason"] == "choice:SHORT" and out["shadow_id"] == "sh-1"
    assert shadows[0][1:] == ("audit:choice:SHORT", "d-BTCUSDT", "audit")


def test_audit_lets_an_agreed_open_through(monkeypatch: Any) -> None:
    monkeypatch.setenv("EVE_PAPER_AUTONOMY", "true")
    monkeypatch.setattr("app.eve.dossier.get_dossier", lambda s, i: None)
    submitted: list[dict[str, Any]] = []
    pilot, _ = _pilot("LONG", submitted, audit=_audit(choice="LONG", score=3.0, noul=0.8))
    report = pilot.run_cycle(MagicMock(), [_prop(action="OPEN", direction="LONG")])
    assert [s["decided_by"] for s in submitted] == ["eve"]
    assert report["symbols"][0]["outcomes"][0]["audit"]["verdict"] == "allow"


def test_same_bar_is_judged_once(monkeypatch: Any) -> None:
    monkeypatch.setenv("EVE_PAPER_AUTONOMY", "true")
    monkeypatch.setattr("app.eve.dossier.get_dossier", lambda s, i: None)
    submitted: list[dict[str, Any]] = []
    pilot, evaluated = _pilot("ABSTAIN", submitted)
    batch = [_prop(action="OPEN", direction="LONG")]
    pilot.run_cycle(MagicMock(), batch)
    second = pilot.run_cycle(MagicMock(), batch)
    assert evaluated == ["BTCUSDT"]
    assert second["skipped_already_judged"] == 1
    # Ève abstained: the engine opens anyway, once.
    assert [x["decided_by"] for x in submitted] == ["engine_over_eve"]


def test_cycle_does_nothing_when_autonomy_off(monkeypatch: Any) -> None:
    monkeypatch.setenv("EVE_PAPER_AUTONOMY", "false")
    submitted: list[dict[str, Any]] = []
    pilot, evaluated = _pilot("LONG", submitted)
    report = pilot.run_cycle(MagicMock(), [_prop(action="OPEN", direction="LONG")])
    assert evaluated == [] and submitted == []
    assert report["autonomy_enabled"] is False


def test_budget_caps_symbols_per_cycle(monkeypatch: Any) -> None:
    monkeypatch.setenv("EVE_PAPER_AUTONOMY", "true")
    monkeypatch.setattr("app.eve.dossier.get_dossier", lambda s, i: None)
    submitted: list[dict[str, Any]] = []
    pilot, evaluated = _pilot("HOLD", submitted)
    pilot.max_symbols_per_cycle = 1
    report = pilot.run_cycle(MagicMock(), [
        _prop(action="OPEN", direction="LONG", symbol="AAA"),
        _prop(action="OPEN", direction="LONG", symbol="BBB"),
    ])
    assert evaluated == ["AAA"]
    assert report["skipped_over_budget"] == 1


def test_engine_closes_over_eve(monkeypatch: Any) -> None:
    monkeypatch.setenv("EVE_PAPER_AUTONOMY", "true")
    monkeypatch.setattr("app.eve.dossier.get_dossier", lambda s, i: None)
    submitted: list[dict[str, Any]] = []
    pilot, _ = _pilot("HOLD", submitted)
    pilot.run_cycle(MagicMock(), [_prop(action="CLOSE", portfolio_code="WIDE", position_id=None)])
    assert [(x["action_override"], x["decided_by"]) for x in submitted] == [("CLOSE", "engine_over_eve")]


def test_shadow_failure_never_breaks_the_cycle(monkeypatch: Any) -> None:
    monkeypatch.setenv("EVE_PAPER_AUTONOMY", "true")
    monkeypatch.setattr("app.eve.dossier.get_dossier", lambda s, i: None)

    def shadow(*a: Any) -> str:
        raise RuntimeError("db down")

    pilot, _ = _pilot("LONG", [], audit=_audit(score=0.0))
    pilot._shadow = shadow
    report = pilot.run_cycle(MagicMock(), [_prop(action="OPEN", direction="LONG")])
    assert report["symbols"][0]["outcomes"][0]["status"] == "blocked_by_audit"
