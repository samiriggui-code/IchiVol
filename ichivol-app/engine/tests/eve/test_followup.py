"""Phase J — follow-up proposals + outcome recording."""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

from app.eve.followup import (
    propose_followup_action,
    record_outcome_from_position,
    run_followup,
    sync_outcomes,
)


def test_propose_close_on_guardian_critical() -> None:
    action, rationale, rejected = propose_followup_action(
        position=SimpleNamespace(status="OPEN", mae_pct=0.0, mfe_pct=0.0, take_profit_price=None, entry_price=100),
        guardian={"warnings": [{"code": "kill_switch_armed", "severity": "critical"}]},
        last_eve_action="LONG",
    )
    assert action == "CLOSE"
    assert "guardian_critical" in rejected


def test_propose_close_on_deep_mae() -> None:
    action, _, rejected = propose_followup_action(
        position=SimpleNamespace(
            status="OPEN",
            mae_pct=-0.04,
            mfe_pct=0.0,
            take_profit_price=110,
            entry_price=100,
        ),
        guardian={"warnings": []},
        last_eve_action="LONG",
    )
    assert action == "CLOSE"
    assert "mae_deep" in rejected


def test_propose_hold_default() -> None:
    action, _, _ = propose_followup_action(
        position=SimpleNamespace(
            status="OPEN",
            mae_pct=-0.005,
            mfe_pct=0.01,
            take_profit_price=110,
            entry_price=100,
        ),
        guardian={"warnings": []},
        last_eve_action="LONG",
    )
    assert action == "HOLD"


def test_shadow_choice_close_escalates() -> None:
    action, _, rejected = propose_followup_action(
        position=SimpleNamespace(
            status="OPEN",
            mae_pct=-0.005,
            mfe_pct=0.01,
            take_profit_price=110,
            entry_price=100,
        ),
        guardian={"warnings": []},
        last_eve_action="LONG",
        shadow={
            "jev": {
                "ok": True,
                "answers": {
                    "review": {"noul": 0.8},
                    "independent_action": {"choice": "CLOSE"},
                    "audit_confidence": {"score": 3},
                },
            }
        },
    )
    assert action == "CLOSE"
    assert "shadow_choice_close" in rejected


def test_propose_abstain_no_position() -> None:
    action, _, rejected = propose_followup_action(
        position=None,
        guardian={"warnings": []},
        last_eve_action="LONG",
    )
    assert action == "ABSTAIN"
    assert "no_position" in rejected


def test_record_outcome_never_touches_decision_time() -> None:
    decision_time = {"captured_at": "2026-01-01T00:00:00+00:00", "known_at": 1}
    dossier = SimpleNamespace(
        id="d1",
        outcome_json=None,
        decision_time_json=decision_time,
        status="open",
        execution_status="opened",
        updated_at=None,
    )
    pos = SimpleNamespace(
        id="p1",
        direction="LONG",
        entry_price=100.0,
        exit_price=105.0,
        exit_reason="manual_close",
        pnl_pct=0.05,
        realized_pnl=40.0,
        entry_fee=1.0,
        exit_fee=1.0,
        mfe_pct=0.06,
        mae_pct=-0.01,
        entry_time=datetime(2026, 1, 1, tzinfo=timezone.utc),
        exit_time=datetime(2026, 1, 2, tzinfo=timezone.utc),
        status="CLOSED",
    )
    session = MagicMock()
    oc = record_outcome_from_position(session, dossier, pos)
    assert oc["lifecycle"] == "closed"
    assert oc["closed"]["realized_pnl"] == 40.0
    assert dossier.decision_time_json is decision_time
    assert dossier.decision_time_json["known_at"] == 1
    assert dossier.status == "closed"


def test_run_followup_records_log(monkeypatch: Any) -> None:
    monkeypatch.setenv("EVE_PAPER_AUTONOMY", "false")
    dossier = SimpleNamespace(
        id="d1",
        symbol="BTCUSDT",
        timeframe="1h",
        eve_action="LONG",
        verdict_id=None,
        outcome_json=None,
        execution_status="opened",
        updated_at=None,
        decision_time_json={"captured_at": "t0"},
    )
    session = MagicMock()
    ctx = {
        "symbol": "BTCUSDT",
        "timeframe": "1h",
        "data_quality": 0.8,
        "facts": [],
        "engines": {},
        "unavailable": [],
        "baseline": {},
    }
    with (
        patch("app.eve.followup.get_dossier", return_value=dossier),
        patch("app.eve.followup.find_linked_position", return_value=None),
        patch("app.eve.context.build_engine_context", return_value=ctx),
        patch("app.eve.followup.run_guardian", return_value={"warnings": []}),
        patch(
            "app.eve.followup.run_shadow_mode",
            return_value={"skipped": True, "primitives_used": [], "jev": {}},
        ),
    ):
        out = run_followup(session, "d1", apply=False, use_jev=False, use_shadow=True)
    assert out["ok"] is True
    assert out["proposed_action"] == "ABSTAIN"
    assert out["shadow"]["used"] is True
    assert dossier.outcome_json["schema"] == "ichivol.eve.outcome.v1"
    assert len(dossier.outcome_json["followups"]) == 1
    assert dossier.outcome_json["followups"][0]["phase"] == "J+K"
    assert dossier.decision_time_json == {"captured_at": "t0"}


def test_sync_outcomes_updates_closed(monkeypatch: Any) -> None:
    dossier = SimpleNamespace(
        id="d9",
        outcome_json=None,
        decision_time_json={"x": 1},
        status="open",
        execution_status="opened",
        updated_at=None,
    )
    pos = SimpleNamespace(
        id="p9",
        status="CLOSED",
        direction="SHORT",
        entry_price=50.0,
        exit_price=48.0,
        exit_reason="stop",
        pnl_pct=0.04,
        realized_pnl=10.0,
        entry_fee=0.5,
        exit_fee=0.5,
        mfe_pct=0.05,
        mae_pct=-0.01,
        entry_time=datetime(2026, 1, 1, tzinfo=timezone.utc),
        exit_time=datetime(2026, 1, 2, tzinfo=timezone.utc),
    )
    session = MagicMock()
    session.scalars.return_value = [dossier]
    with patch("app.eve.followup.find_linked_position", return_value=pos):
        out = sync_outcomes(session, limit=10)
    assert out["updated_count"] == 1
    assert dossier.outcome_json["closed"]["position_id"] == "p9"
    assert dossier.decision_time_json == {"x": 1}
