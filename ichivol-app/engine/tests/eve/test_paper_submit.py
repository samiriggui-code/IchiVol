"""V2 paper_submit — Risk Kernel dry-run; autonomy off by default."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

from app.eve.paper_submit import autonomy_enabled, submit_paper_from_dossier


def test_autonomy_default_off(monkeypatch: Any) -> None:
    monkeypatch.setenv("EVE_PAPER_AUTONOMY", "false")
    assert autonomy_enabled() is False


def test_autonomy_env_on(monkeypatch: Any) -> None:
    monkeypatch.setenv("EVE_PAPER_AUTONOMY", "true")
    assert autonomy_enabled() is True


def test_submit_dry_run_when_autonomy_off(monkeypatch: Any) -> None:
    monkeypatch.setenv("EVE_PAPER_AUTONOMY", "false")

    dossier = SimpleNamespace(
        id="d1",
        symbol="BTCUSDT",
        timeframe="1h",
        eve_action="LONG",
        verdict_id="v1",
        context_json={
            "facts": [
                {"id": "m.price", "field": "price", "value": 100.0, "status": "ok"},
                {"id": "m.atr_stop", "field": "suggested_stop_distance", "value": 2.0, "status": "ok"},
            ]
        },
        execution_status="not_executed",
    )
    verdict = SimpleNamespace(
        action="LONG",
        status="potential",
        body_json={},
    )
    portfolio = SimpleNamespace(
        id="pf1",
        cash=5000.0,
        strategy_profile={"risk_pct": 0.01, "max_notional_pct": 0.25, "max_open_positions": 5},
        kill_switch_armed=False,
        daily_loss_locked=False,
    )
    rk_ok = {
        "accepted": True,
        "codes": [],
        "sized": {"qty": 1.0, "notional": 100.0},
        "kernel_version": "risk_kernel_v1",
    }

    session = MagicMock()
    with (
        patch("app.eve.paper_submit.get_dossier", return_value=dossier),
        patch("app.eve.paper_submit.get_verdict", return_value=verdict),
        patch("app.eve.paper_submit._resolve_portfolio", return_value=portfolio),
        patch("app.eve.paper_submit.evaluate_risk_kernel_for_plan", return_value=rk_ok),
        patch("app.eve.paper_submit.paper_engine.open_user_confirmed") as open_fn,
    ):
        out = submit_paper_from_dossier(session, "d1", execute=None)

    assert out["ok"] is True
    assert out["status"] == "dry_run_autonomy_off"
    assert out["executed"] is False
    assert out["order_submitted"] is False
    assert out["risk_authorization"] == "accepted_dry_run"
    assert dossier.execution_status == "dry_run_autonomy_off"
    open_fn.assert_not_called()


def test_submit_skips_hold(monkeypatch: Any) -> None:
    monkeypatch.setenv("EVE_PAPER_AUTONOMY", "false")
    dossier = SimpleNamespace(
        id="d2",
        symbol="ETHUSDT",
        timeframe="1h",
        eve_action="HOLD",
        verdict_id=None,
        context_json={},
        execution_status="not_executed",
    )
    session = MagicMock()
    with patch("app.eve.paper_submit.get_dossier", return_value=dossier):
        out = submit_paper_from_dossier(session, "d2")
    assert out["status"] == "skipped_hold"
    assert out["executed"] is False


def test_submit_skips_abstain(monkeypatch: Any) -> None:
    monkeypatch.setenv("EVE_PAPER_AUTONOMY", "false")
    dossier = SimpleNamespace(
        id="d3",
        symbol="ETHUSDT",
        timeframe="1h",
        eve_action="ABSTAIN",
        verdict_id=None,
        context_json={},
        execution_status="not_executed",
    )
    session = MagicMock()
    with patch("app.eve.paper_submit.get_dossier", return_value=dossier):
        out = submit_paper_from_dossier(session, "d3")
    assert out["status"] == "skipped_abstain"


def test_close_dry_run_no_position(monkeypatch: Any) -> None:
    monkeypatch.setenv("EVE_PAPER_AUTONOMY", "false")
    dossier = SimpleNamespace(
        id="d4",
        symbol="BTCUSDT",
        timeframe="1h",
        eve_action="CLOSE",
        verdict_id=None,
        context_json={"facts": [{"field": "price", "value": 50.0}]},
        execution_status="not_executed",
    )
    portfolio = SimpleNamespace(id="pf1", strategy_profile={})
    session = MagicMock()
    with (
        patch("app.eve.paper_submit.get_dossier", return_value=dossier),
        patch("app.eve.paper_submit._resolve_portfolio", return_value=portfolio),
        patch("app.eve.paper_submit._find_open_position", return_value=None),
    ):
        out = submit_paper_from_dossier(session, "d4", allow_screener=False)
    assert out["status"] == "close_no_position"
    assert out["executed"] is False


def test_close_dry_run_with_position(monkeypatch: Any) -> None:
    monkeypatch.setenv("EVE_PAPER_AUTONOMY", "false")
    dossier = SimpleNamespace(
        id="d5",
        symbol="BTCUSDT",
        timeframe="1h",
        eve_action="CLOSE",
        verdict_id=None,
        context_json={"facts": [{"field": "price", "value": 50.0}]},
        execution_status="not_executed",
    )
    portfolio = SimpleNamespace(id="pf1", strategy_profile={})
    open_pos = SimpleNamespace(id="pos-1")
    session = MagicMock()
    with (
        patch("app.eve.paper_submit.get_dossier", return_value=dossier),
        patch("app.eve.paper_submit._resolve_portfolio", return_value=portfolio),
        patch("app.eve.paper_submit._find_open_position", return_value=open_pos),
        patch("app.eve.paper_submit.paper_engine.close_manually") as close_fn,
    ):
        out = submit_paper_from_dossier(session, "d5", allow_screener=False)
    assert out["status"] == "dry_run_close"
    assert out["would_close_position_id"] == "pos-1"
    close_fn.assert_not_called()


def test_execute_forced_off_when_autonomy_off(monkeypatch: Any) -> None:
    monkeypatch.setenv("EVE_PAPER_AUTONOMY", "false")
    dossier = SimpleNamespace(
        id="d6",
        symbol="BTCUSDT",
        timeframe="1h",
        eve_action="LONG",
        verdict_id=None,
        context_json={
            "facts": [
                {"field": "price", "value": 100.0},
                {"field": "suggested_stop_distance", "value": 2.0},
            ]
        },
        execution_status="not_executed",
    )
    portfolio = SimpleNamespace(
        id="pf1",
        cash=5000.0,
        strategy_profile={},
        kill_switch_armed=False,
        daily_loss_locked=False,
    )
    rk_ok = {"accepted": True, "codes": [], "sized": None, "kernel_version": "risk_kernel_v1"}
    session = MagicMock()
    with (
        patch("app.eve.paper_submit.get_dossier", return_value=dossier),
        patch("app.eve.paper_submit._resolve_portfolio", return_value=portfolio),
        patch("app.eve.paper_submit.evaluate_risk_kernel_for_plan", return_value=rk_ok),
        patch("app.eve.paper_submit.paper_engine.open_user_confirmed") as open_fn,
    ):
        out = submit_paper_from_dossier(session, "d6", execute=True, allow_screener=False)
    assert out["status"] == "dry_run_autonomy_off"
    assert out["execute_requested"] is False
    open_fn.assert_not_called()
