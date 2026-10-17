"""Light Ève judgement view for the « Moteur vs Ève » page."""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace

from app.eve.dossier import decision_summary


def test_summary_keeps_engine_proposals_and_drops_heavy_payloads():
    proposals = [
        {"portfolio_code": "ICHIVOL_BASELINE_V1", "engine_action": "OPEN", "engine_direction": "LONG",
         "eve_action": "ABSTAIN", "eve_accepts": False, "status": "refused_by_eve", "executed": False},
    ]
    dossier = SimpleNamespace(
        id="d1", created_at=datetime(2026, 10, 17, 9, tzinfo=timezone.utc), symbol="BTCUSDT", timeframe="1h",
        baseline_decision="BUY", eve_action="ABSTAIN", execution_status="skipped_abstain",
        decision_time_json={
            "engine_proposals": proposals,
            "degradation": {"level": "healthy"},
            "entry_gate": {"decision": "skipped", "reason": "non_entry_action", "checks": [1, 2]},
        },
        context_json={"facts": ["heavy"] * 60},
    )
    verdict = SimpleNamespace(reasoning="x" * 1000, coherence_score=0.42)

    out = decision_summary(dossier, verdict)

    assert out["engine_proposals"] == proposals
    assert out["entry_gate"] == {"decision": "skipped", "reason": "non_entry_action"}
    assert out["degradation"] == "healthy" and out["coherence"] == 0.42
    assert len(out["reasoning"]) == 400
    assert "context" not in out and "facts" not in out


def test_summary_without_verdict_or_proposals():
    dossier = SimpleNamespace(
        id="d2", created_at=None, symbol="EURUSD", timeframe="1h", baseline_decision=None, eve_action=None,
        execution_status="not_executed", decision_time_json=None,
    )
    out = decision_summary(dossier)
    assert out["engine_proposals"] == [] and out["reasoning"] is None and out["entry_gate"] is None
