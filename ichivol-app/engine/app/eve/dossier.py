"""Dossier IchiVol + Verdict persistence (Postgres)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import EveDossier, EveVerdict


def persist_dossier(
    session: Session,
    *,
    payload: dict[str, Any],
) -> EveDossier:
    """Persist a full evaluation dossier. Separates decision-time vs post-outcome."""
    now = datetime.now(timezone.utc)
    dossier = EveDossier(
        symbol=str(payload["symbol"]).upper(),
        timeframe=str(payload.get("timeframe") or "1h"),
        status=str(payload.get("status") or "open"),
        context_json=payload.get("context") or {},
        modes_json=payload.get("modes") or {},
        jev_json=payload.get("jev") or {},
        coherence_json=payload.get("coherence") or {},
        policy_json=payload.get("policy") or {},
        decision_time_json=payload.get("decision_time") or {},
        outcome_json=None,
        baseline_decision=payload.get("baseline_decision"),
        eve_action=payload.get("eve_action"),
        execution_status="not_executed",
        created_at=now,
        updated_at=now,
    )
    session.add(dossier)
    session.flush()

    verdict_payload = payload.get("verdict") or {}
    verdict = EveVerdict(
        dossier_id=dossier.id,
        action=str(verdict_payload.get("action") or payload.get("eve_action") or "ABSTAIN"),
        status=str(verdict_payload.get("status") or "potential"),
        scenario_retained=verdict_payload.get("scenario_retained"),
        scenarios_rejected=verdict_payload.get("scenarios_rejected") or [],
        reasoning=verdict_payload.get("reasoning"),
        coherence_score=verdict_payload.get("coherence_score"),
        body_json=verdict_payload,
        created_at=now,
    )
    session.add(verdict)
    session.flush()
    dossier.verdict_id = verdict.id
    session.flush()
    return dossier


def build_dossier_timeline(dossier: EveDossier) -> list[dict[str, Any]]:
    """Timeline decision_time → followups → closed outcome (handoff §7.B.3).

    Inspired by jarrodwatts event stream + buberlo (state, decision, outcome)
    triples — display only; never mutates ``decision_time_json``.
    """
    events: list[dict[str, Any]] = []
    created = dossier.created_at.isoformat() if dossier.created_at else None
    dt = dossier.decision_time_json if isinstance(dossier.decision_time_json, dict) else {}
    events.append(
        {
            "kind": "decision",
            "at": dt.get("at") or created,
            "action": dossier.eve_action,
            "baseline": dossier.baseline_decision,
            "execution_status": dossier.execution_status,
            "detail": dt.get("rationale") or dt.get("reasoning"),
        }
    )
    oc = dossier.outcome_json if isinstance(dossier.outcome_json, dict) else {}
    for fu in oc.get("followups") or []:
        if not isinstance(fu, dict):
            continue
        events.append(
            {
                "kind": "followup",
                "at": fu.get("at"),
                "action": fu.get("proposed_action"),
                "detail": fu.get("rationale"),
                "phase": fu.get("phase"),
                "shadow": fu.get("shadow"),
                "rejected": fu.get("rejected") or [],
            }
        )
    closed = oc.get("closed") if isinstance(oc.get("closed"), dict) else None
    if closed:
        events.append(
            {
                "kind": "outcome",
                "at": closed.get("closed_at") or closed.get("at") or oc.get("last_followup"),
                "action": "CLOSED",
                "detail": closed.get("reason") or closed.get("close_reason"),
                "realized_pnl": closed.get("realized_pnl"),
                "realized_pnl_pct": closed.get("realized_pnl_pct") or closed.get("pnl_pct"),
                "fees": closed.get("fees"),
            }
        )
    return events


def dossier_to_dict(dossier: EveDossier, verdict: EveVerdict | None = None) -> dict[str, Any]:
    v = verdict
    if v is None and dossier.verdict_id:
        # relationship may be loaded by caller
        pass
    out: dict[str, Any] = {
        "id": dossier.id,
        "symbol": dossier.symbol,
        "timeframe": dossier.timeframe,
        "status": dossier.status,
        "baseline_decision": dossier.baseline_decision,
        "eve_action": dossier.eve_action,
        "execution_status": dossier.execution_status,
        "context": dossier.context_json,
        "modes": dossier.modes_json,
        "jev": dossier.jev_json,
        "coherence": dossier.coherence_json,
        "policy": dossier.policy_json,
        "decision_time": dossier.decision_time_json,
        "outcome": dossier.outcome_json,
        "timeline": build_dossier_timeline(dossier),
        "created_at": dossier.created_at.isoformat() if dossier.created_at else None,
        "updated_at": dossier.updated_at.isoformat() if dossier.updated_at else None,
        "verdict_id": dossier.verdict_id,
    }
    if v is not None:
        out["verdict"] = verdict_to_dict(v)
    return out


def verdict_to_dict(verdict: EveVerdict) -> dict[str, Any]:
    return {
        "id": verdict.id,
        "dossier_id": verdict.dossier_id,
        "action": verdict.action,
        "status": verdict.status,
        "scenario_retained": verdict.scenario_retained,
        "scenarios_rejected": verdict.scenarios_rejected,
        "reasoning": verdict.reasoning,
        "coherence_score": verdict.coherence_score,
        "body": verdict.body_json,
        "created_at": verdict.created_at.isoformat() if verdict.created_at else None,
    }


def list_dossiers(
    session: Session, *, limit: int = 20, symbol: str | None = None, max_limit: int = 100
) -> list[EveDossier]:
    stmt = select(EveDossier).order_by(EveDossier.created_at.desc()).limit(min(max(limit, 1), max_limit))
    if symbol:
        stmt = stmt.where(EveDossier.symbol == symbol.upper())
    return list(session.scalars(stmt))


def decision_summary(dossier: EveDossier, verdict: EveVerdict | None = None) -> dict[str, Any]:
    """Light view of one Ève judgement for the « Moteur vs Ève » page: what the engine proposed on each book,
    what Ève answered and what happened. No context/facts payload (those stay in the full dossier)."""
    dt = dossier.decision_time_json if isinstance(dossier.decision_time_json, dict) else {}
    deg = dt.get("degradation") if isinstance(dt.get("degradation"), dict) else {}
    gate = dt.get("entry_gate") if isinstance(dt.get("entry_gate"), dict) else {}
    proposals = [p for p in (dt.get("engine_proposals") or []) if isinstance(p, dict)]
    reasoning = verdict.reasoning if verdict is not None else None
    return {
        "id": dossier.id,
        "created_at": dossier.created_at.isoformat() if dossier.created_at else None,
        "symbol": dossier.symbol,
        "timeframe": dossier.timeframe,
        "baseline_decision": dossier.baseline_decision,
        "eve_action": dossier.eve_action,
        "execution_status": dossier.execution_status,
        "degradation": deg.get("level"),
        "entry_gate": {"decision": gate.get("decision"), "reason": gate.get("reason")} if gate else None,
        "coherence": verdict.coherence_score if verdict is not None else None,
        "reasoning": reasoning[:400] if isinstance(reasoning, str) else None,
        "engine_proposals": proposals,
    }


def get_dossier(session: Session, dossier_id: str) -> EveDossier | None:
    return session.get(EveDossier, dossier_id)


def get_verdict(session: Session, verdict_id: str) -> EveVerdict | None:
    return session.get(EveVerdict, verdict_id)
