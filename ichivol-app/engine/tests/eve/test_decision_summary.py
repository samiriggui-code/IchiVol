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

    assert out["engine_proposals"] == [{**proposals[0], "result": None}]
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


def test_summary_attaches_trade_results_why_and_opinions():
    proposals = [
        {"portfolio_code": "A", "engine_action": "OPEN", "engine_direction": "LONG", "eve_action": "ABSTAIN",
         "eve_accepts": False, "decided_by": "engine_over_eve", "position_id": "p1"},
        {"portfolio_code": "B", "engine_action": "OPEN", "engine_direction": "LONG", "eve_action": "ABSTAIN",
         "eve_accepts": False, "status": "refused_by_eve", "shadow_id": "s1"},
    ]
    modes = {
        "analyst": {"hypotheses": {"primary_action": "LONG"}},
        "challenger": {"contradictions": [], "jev": {"ok": True, "answers": {
            "alt_action": {"choice": "ABSTAIN"}, "baseline_fragile": {"noul": 0.62}}}},
        "guardian": {"warnings": [], "jev": {"ok": True, "answers": {
            "risk_stance": {"choice": "ALLOW"}, "risk_level": {"score": 2}}}},
        "shadow": {"jev": {"ok": True, "answers": {"independent_action": {"choice": "LONG"},
                                                    "audit_confidence": {"score": 3}}}},
        "synthesis": {"rejected_scenarios": ["baseline:LONG"]},
    }
    dossier = SimpleNamespace(
        id="d3", created_at=None, symbol="BTCUSDT", timeframe="1h", baseline_decision="BUY", eve_action="ABSTAIN",
        execution_status="skipped_abstain", decision_time_json={"engine_proposals": proposals}, modes_json=modes,
    )
    results = {"p1": {"kind": "position", "status": "CLOSED", "pnl_r": -1.0}, "s1": {"kind": "shadow"}}
    out = decision_summary(
        dossier, SimpleNamespace(reasoning="Synthesized from Analyst/Challenger/Guardian (potential only)",
                                 coherence_score=0.88), results=results,
    )
    assert [p["result"] for p in out["engine_proposals"]] == [results["p1"], results["s1"]]
    assert out["why"] == "Le contradicteur jugeait plus prudent de s’abstenir, Ève l’a suivi."
    stances = {o["who"]: o["stance"] for o in out["opinions"]}
    assert stances == {"analyst": "pour", "challenger": "contre", "guardian": "pour", "audit": "pour"}
    challenger = next(o for o in out["opinions"] if o["who"] == "challenger")
    assert "signal du moteur fragile à 62 %" in challenger["details"]


def test_trade_result_in_r_for_a_paper_lot():
    from app.eve.dossier import trade_result

    lot = SimpleNamespace(status="CLOSED", exit_reason="stop_hit", realized_pnl=-50.0, risk_amount=50.0, pnl_pct=-0.02)
    assert trade_result(lot)["pnl_r"] == -1.0 and trade_result(lot)["kind"] == "position"
