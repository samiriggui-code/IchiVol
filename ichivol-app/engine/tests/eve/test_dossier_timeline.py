"""Timeline dossier — decision → followups → outcome."""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

from app.eve.dossier import build_dossier_timeline


def test_timeline_decision_followup_outcome() -> None:
    created = datetime(2026, 10, 16, 12, 0, tzinfo=timezone.utc)
    dossier = SimpleNamespace(
        created_at=created,
        eve_action="LONG",
        baseline_decision="BUY",
        execution_status="dry_run",
        decision_time_json={"at": "2026-10-16T12:00:00+00:00", "rationale": "setup ok"},
        outcome_json={
            "followups": [
                {
                    "at": "2026-10-16T13:00:00+00:00",
                    "proposed_action": "HOLD",
                    "rationale": "MAE shallow",
                    "phase": "J+K",
                    "rejected": [],
                    "shadow": {"choice": "HOLD"},
                }
            ],
            "closed": {
                "closed_at": "2026-10-16T15:00:00+00:00",
                "realized_pnl": 12.5,
                "pnl_pct": 0.02,
                "fees": 0.4,
                "reason": "tp",
            },
        },
    )
    events = build_dossier_timeline(dossier)  # type: ignore[arg-type]
    assert [e["kind"] for e in events] == ["decision", "followup", "outcome"]
    assert events[0]["action"] == "LONG"
    assert events[1]["action"] == "HOLD"
    assert events[2]["realized_pnl"] == 12.5


def test_timeline_decision_only() -> None:
    dossier = SimpleNamespace(
        created_at=None,
        eve_action="ABSTAIN",
        baseline_decision=None,
        execution_status="not_executed",
        decision_time_json={},
        outcome_json=None,
    )
    events = build_dossier_timeline(dossier)  # type: ignore[arg-type]
    assert len(events) == 1
    assert events[0]["kind"] == "decision"
    assert events[0]["action"] == "ABSTAIN"
