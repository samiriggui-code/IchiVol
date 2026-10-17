"""Ève autopilot — the engine proposes per book, Ève accepts or refuses, once per closed bar."""

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


def _pilot(eve_action: str, submitted: list[dict[str, Any]]) -> tuple[EveAutopilot, list[str]]:
    evaluated: list[str] = []

    def evaluate(symbol: str, timeframe: str, **kw: Any) -> dict[str, Any]:
        evaluated.append(symbol)
        assert kw["paper_dry_run"] is False  # the evaluation itself never trades
        return {"eve_action": eve_action, "dossier_id": f"d-{symbol}"}

    def submit(session: Any, dossier_id: str, **kw: Any) -> dict[str, Any]:
        submitted.append({"dossier_id": dossier_id, **kw})
        return {"status": "opened", "executed": True, "risk_authorization": "accepted"}

    return EveAutopilot(evaluate=evaluate, submit=submit), evaluated


def test_cycle_opens_only_on_books_that_proposed_and_when_eve_agrees(monkeypatch: Any) -> None:
    monkeypatch.setenv("EVE_PAPER_AUTONOMY", "true")
    monkeypatch.setattr("app.eve.dossier.get_dossier", lambda s, i: None)
    submitted: list[dict[str, Any]] = []
    pilot, evaluated = _pilot("LONG", submitted)
    report = pilot.run_cycle(MagicMock(), [
        _prop(action="OPEN", direction="LONG", portfolio_code="BASE"),
        _prop(action="OPEN", direction="SHORT", portfolio_code="SESS", engine_decision="SELL"),
    ])
    assert evaluated == ["BTCUSDT"]  # one Ève evaluation per symbol, not per book
    assert [s["portfolio_code"] for s in submitted] == ["BASE"]
    assert submitted[0]["execute"] is True and submitted[0]["action_override"] is None
    outcomes = report["symbols"][0]["outcomes"]
    assert [(o["portfolio_code"], o["eve_accepts"], o["status"]) for o in outcomes] == [
        ("BASE", True, "opened"), ("SESS", False, "refused_by_eve"),
    ]


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
    assert submitted == []  # Ève abstained: nothing opened


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
