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
    assert out["status"] == "skipped_non_directional"
    assert out["executed"] is False
