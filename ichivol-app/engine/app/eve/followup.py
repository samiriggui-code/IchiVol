"""Phase J/K — Eve position follow-up + Shadow audit + outcome recording.

Surveillance only by default. Applying CLOSE goes through ``paper_submit`` and
still respects ``EVE_PAPER_AUTONOMY``. Never mutates ``decision_time_json``.
Never creates an Eve portfolio. Never live trading.

Phase K: Ève Shadow runs an independent counter-evaluation during follow-up;
results are stored on the dossier outcome log (≠ ShadowBroker).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import EveDossier, PaperPosition
from app.eve.actions import EveAction, normalize_action
from app.eve.dossier import build_dossier_timeline, get_dossier, get_verdict
from app.eve.modes import _shadow_answers, run_guardian, run_shadow_mode
from app.eve.paper_submit import autonomy_enabled, submit_paper_from_dossier
from app.paper.portfolio import ensure_baseline_portfolio, get_portfolio_by_code
from app.paper.strategy_profiles import BASELINE_CODE

OUTCOME_SCHEMA = "ichivol.eve.outcome.v1"
FOLLOWUP_SCHEMA = "ichivol.eve.followup.v1"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _outcome_bucket(dossier: EveDossier) -> dict[str, Any]:
    raw = dossier.outcome_json
    if isinstance(raw, dict) and raw.get("schema") == OUTCOME_SCHEMA:
        return dict(raw)
    return {
        "schema": OUTCOME_SCHEMA,
        "lifecycle": "monitoring",
        "followups": [],
        "position_id": None,
        "closed": None,
        "not": ["decision_time_backfill"],
    }


def _position_snapshot(pos: PaperPosition) -> dict[str, Any]:
    signal = pos.entry_signal if isinstance(pos.entry_signal, dict) else {}
    return {
        "id": pos.id,
        "symbol": pos.symbol,
        "timeframe": pos.timeframe,
        "direction": pos.direction,
        "status": pos.status,
        "entry_price": pos.entry_price,
        "entry_time": pos.entry_time.isoformat() if pos.entry_time else None,
        "exit_price": pos.exit_price,
        "exit_time": pos.exit_time.isoformat() if pos.exit_time else None,
        "exit_reason": pos.exit_reason,
        "pnl_pct": pos.pnl_pct,
        "realized_pnl": pos.realized_pnl,
        "mfe_pct": pos.mfe_pct,
        "mae_pct": pos.mae_pct,
        "stop_price": pos.stop_price,
        "take_profit_price": pos.take_profit_price,
        "qty": pos.qty,
        "notional": pos.notional,
        "entry_fee": pos.entry_fee,
        "exit_fee": pos.exit_fee,
        "eve_dossier_id": signal.get("eve_dossier_id"),
        "eve_action": signal.get("eve_action"),
        "user_id": pos.user_id,
        "source": pos.source,
        "portfolio_id": pos.portfolio_id,
    }


def find_linked_position(session: Session, dossier: EveDossier) -> PaperPosition | None:
    """Resolve paper position for a dossier (signal tag or verdict body)."""
    verdict = get_verdict(session, dossier.verdict_id) if dossier.verdict_id else None
    body = (verdict.body_json or {}) if verdict else {}
    pid = body.get("position_id") or (_outcome_bucket(dossier).get("position_id"))
    if pid:
        pos = session.get(PaperPosition, str(pid))
        if pos is not None:
            return pos

    # Scan recent positions tagged with this dossier.
    stmt = (
        select(PaperPosition)
        .where(PaperPosition.symbol == dossier.symbol.upper())
        .order_by(PaperPosition.entry_time.desc())
        .limit(40)
    )
    for pos in session.scalars(stmt):
        signal = pos.entry_signal if isinstance(pos.entry_signal, dict) else {}
        if signal.get("eve_dossier_id") == dossier.id:
            return pos
    return None


def list_tracked(
    session: Session,
    *,
    portfolio_code: str = BASELINE_CODE,
    limit: int = 30,
) -> dict[str, Any]:
    """Open Eve-linked positions + dossiers awaiting outcome."""
    portfolio = get_portfolio_by_code(session, portfolio_code)
    if portfolio is None and portfolio_code == BASELINE_CODE:
        portfolio = ensure_baseline_portfolio(session)

    open_eve: list[dict[str, Any]] = []
    if portfolio is not None:
        stmt = (
            select(PaperPosition)
            .where(
                PaperPosition.portfolio_id == portfolio.id,
                PaperPosition.status == "OPEN",
            )
            .order_by(PaperPosition.entry_time.desc())
            .limit(100)
        )
        for pos in session.scalars(stmt):
            signal = pos.entry_signal if isinstance(pos.entry_signal, dict) else {}
            if signal.get("eve_dossier_id") or pos.user_id == "eve_intelligence":
                open_eve.append(_position_snapshot(pos))

    # Dossiers with paper activity but no final outcome yet.
    pending: list[dict[str, Any]] = []
    d_stmt = (
        select(EveDossier)
        .where(EveDossier.execution_status.in_(("opened", "already_open", "closed", "dry_run_autonomy_off", "dry_run_close")))
        .order_by(EveDossier.created_at.desc())
        .limit(min(max(limit, 1), 100))
    )
    for d in session.scalars(d_stmt):
        oc = _outcome_bucket(d)
        pending.append(
            {
                "dossier_id": d.id,
                "symbol": d.symbol,
                "timeframe": d.timeframe,
                "eve_action": d.eve_action,
                "execution_status": d.execution_status,
                "lifecycle": oc.get("lifecycle"),
                "followup_count": len(oc.get("followups") or []),
                "has_final_outcome": oc.get("closed") is not None,
                "created_at": d.created_at.isoformat() if d.created_at else None,
            }
        )

    return {
        "schema": "ichivol.eve.followup_list.v1",
        "portfolio_code": portfolio_code,
        "autonomy_enabled": autonomy_enabled(),
        "open_eve_positions": open_eve[:limit],
        "dossiers": pending,
        "note": "Phase J — surveillance; CLOSE apply gated by EVE_PAPER_AUTONOMY",
    }


def propose_followup_action(
    *,
    position: PaperPosition | None,
    guardian: dict[str, Any],
    last_eve_action: str | None,
    shadow: dict[str, Any] | None = None,
) -> tuple[EveAction, str, list[str]]:
    """Deterministic follow-up: HOLD / CLOSE / ABSTAIN (never LONG/SHORT here).

    Phase K Shadow signals can escalate HOLD → CLOSE / ABSTAIN, never open risk.
    """
    rejected: list[str] = []
    warnings = guardian.get("warnings") or []
    critical = [w for w in warnings if w.get("severity") == "critical"]

    if critical:
        return "CLOSE", "Guardian critical while position open → propose CLOSE", ["guardian_critical"]

    if position is None:
        return "ABSTAIN", "No linked open position → abstain from intervention", ["no_position"]

    if position.status != "OPEN":
        return "ABSTAIN", "Position already closed → no intervention", ["already_closed"]

    mae = position.mae_pct
    mfe = position.mfe_pct
    # Deep adverse excursion vs entry → prefer exit review
    if isinstance(mae, (int, float)) and mae <= -0.03:
        rejected.append("mae_deep")
        return "CLOSE", f"MAE {mae:.2%} deep → propose CLOSE", rejected

    # Phase K — independent Shadow audit on an open book.
    if shadow:
        answers = _shadow_answers(shadow)
        noul = (answers.get("review") or {}).get("noul")
        choice = normalize_action((answers.get("independent_action") or {}).get("choice"))
        score = (answers.get("audit_confidence") or {}).get("score")
        if choice == "CLOSE":
            rejected.append("shadow_choice_close")
            return "CLOSE", "Shadow CHOICE CLOSE → propose CLOSE", rejected
        if isinstance(score, (int, float)) and score <= 1:
            rejected.append("shadow_low_audit_confidence")
            return "CLOSE", "Shadow SCORE weak on open book → propose CLOSE", rejected
        if isinstance(noul, (int, float)) and noul < 0.35:
            rejected.append("shadow_noul_low")
            return "CLOSE", "Shadow NOUL low coherence → propose CLOSE", rejected
        if choice == "ABSTAIN":
            rejected.append("shadow_choice_abstain")
            return "ABSTAIN", "Shadow CHOICE ABSTAIN → no intervention", rejected

    # Near take-profit: HOLD (let protection / TP work) unless guardian warned
    if (
        position.take_profit_price
        and position.entry_price
        and isinstance(mfe, (int, float))
        and mfe >= 0.02
    ):
        return "HOLD", f"MFE {mfe:.2%} constructive → HOLD", rejected

    if last_eve_action == "CLOSE":
        return "CLOSE", "Prior Eve action was CLOSE → maintain close proposal", rejected

    return "HOLD", "No critical risk flag → HOLD", rejected


def run_followup(
    session: Session,
    dossier_id: str,
    *,
    apply: bool = False,
    use_jev: bool = False,
    use_shadow: bool = True,
) -> dict[str, Any]:
    """Review one dossier/position and propose HOLD/CLOSE/ABSTAIN.

    Phase K runs Ève Shadow (independent) when ``use_shadow`` is true.
    ``apply=True`` only submits CLOSE via paper_submit when autonomy is on;
    otherwise records a dry-run proposal.
    """
    dossier = get_dossier(session, dossier_id)
    if dossier is None:
        return {"ok": False, "error": "dossier_not_found", "dossier_id": dossier_id}

    position = find_linked_position(session, dossier)
    # Lightweight context for Guardian (+ Shadow) — avoid full evaluate cost.
    from app.eve.context import build_engine_context

    context = build_engine_context(dossier.symbol, dossier.timeframe)
    guardian = run_guardian(context, use_jev=use_jev)
    shadow: dict[str, Any] | None = None
    if use_shadow:
        shadow = run_shadow_mode(context, use_jev=use_jev)

    action, rationale, rejected = propose_followup_action(
        position=position,
        guardian=guardian,
        last_eve_action=dossier.eve_action,
        shadow=shadow,
    )

    shadow_answers = _shadow_answers(shadow) if shadow else {}
    report: dict[str, Any] = {
        "schema": FOLLOWUP_SCHEMA,
        "dossier_id": dossier_id,
        "symbol": dossier.symbol,
        "timeframe": dossier.timeframe,
        "proposed_action": action,
        "rationale": rationale,
        "rejected_scenarios": rejected,
        "position": _position_snapshot(position) if position else None,
        "guardian_warning_count": len(guardian.get("warnings") or []),
        "shadow": {
            "used": bool(shadow),
            "skipped": bool(shadow and shadow.get("skipped")),
            "primitives_used": (shadow or {}).get("primitives_used") or [],
            "noul": (shadow_answers.get("review") or {}).get("noul"),
            "choice": (shadow_answers.get("independent_action") or {}).get("choice"),
            "score": (shadow_answers.get("audit_confidence") or {}).get("score"),
            "not": "shadow_broker",
        },
        "autonomy_enabled": autonomy_enabled(),
        "apply_requested": bool(apply),
        "applied": False,
        "paper_submit": None,
        "reviewed_at": _now_iso(),
        "status": "potential",
        "executed": False,
        "note": "Phase J/K potential — Shadow audit recorded; Risk Kernel / close gated",
    }

    oc = _outcome_bucket(dossier)
    if position is not None:
        oc["position_id"] = position.id
    followups = list(oc.get("followups") or [])
    followups.append(
        {
            "at": report["reviewed_at"],
            "proposed_action": action,
            "rationale": rationale,
            "rejected": rejected,
            "position_status": position.status if position else None,
            "shadow": report["shadow"],
            "phase": "J+K",
        }
    )
    oc["followups"] = followups[-20:]  # keep last 20
    oc["lifecycle"] = "monitoring" if (position and position.status == "OPEN") else oc.get("lifecycle") or "monitoring"
    oc["last_followup"] = report["reviewed_at"]
    oc["last_shadow"] = report["shadow"]
    dossier.outcome_json = oc
    dossier.updated_at = datetime.now(timezone.utc)

    # Optional apply: only CLOSE is actionable here; HOLD/ABSTAIN are no-ops.
    if apply and action == "CLOSE":
        paper = submit_paper_from_dossier(
            session,
            dossier_id,
            portfolio_code=None,  # tous les portefeuilles virtuels
            execute=None,  # respects autonomy hard-gate
            allow_screener=True,
            action_override="CLOSE",
        )
        report["paper_submit"] = paper
        report["applied"] = bool(paper.get("executed"))
        report["executed"] = report["applied"]
        if paper.get("status") in ("dry_run_close", "closed", "close_no_position"):
            report["status"] = paper.get("status")
        session.flush()
    elif apply and action in ("HOLD", "ABSTAIN"):
        report["status"] = f"apply_noop_{action.lower()}"
        report["note"] = f"{action} requires no order"

    # If position already closed, record final outcome metrics.
    if position is not None and position.status == "CLOSED" and not oc.get("closed"):
        oc = record_outcome_from_position(session, dossier, position, flush=False)
        report["outcome"] = oc.get("closed")

    session.flush()
    report["ok"] = True
    return report


def record_outcome_from_position(
    session: Session,
    dossier: EveDossier,
    position: PaperPosition,
    *,
    flush: bool = True,
) -> dict[str, Any]:
    """Write final outcome from a CLOSED paper position. Never touches decision_time."""
    oc = _outcome_bucket(dossier)
    closed = {
        "position_id": position.id,
        "direction": position.direction,
        "entry_price": position.entry_price,
        "exit_price": position.exit_price,
        "exit_reason": position.exit_reason,
        "pnl_pct": position.pnl_pct,
        "realized_pnl": position.realized_pnl,
        "entry_fee": position.entry_fee,
        "exit_fee": position.exit_fee,
        "mfe_pct": position.mfe_pct,
        "mae_pct": position.mae_pct,
        "entry_time": position.entry_time.isoformat() if position.entry_time else None,
        "exit_time": position.exit_time.isoformat() if position.exit_time else None,
        "recorded_at": _now_iso(),
        "net_of_fees": True,
    }
    oc["position_id"] = position.id
    oc["closed"] = closed
    oc["lifecycle"] = "closed"
    dossier.outcome_json = oc
    dossier.status = "closed"
    if dossier.execution_status not in ("closed",):
        # Keep opened if still open path; mark closed when outcome recorded from CLOSED pos
        dossier.execution_status = "closed"
    dossier.updated_at = datetime.now(timezone.utc)
    if flush:
        session.flush()
    return oc


def sync_outcomes(session: Session, *, limit: int = 50) -> dict[str, Any]:
    """Fill outcome_json for dossiers whose linked positions are CLOSED."""
    updated: list[str] = []
    skipped: list[str] = []
    stmt = (
        select(EveDossier)
        .order_by(EveDossier.created_at.desc())
        .limit(min(max(limit, 1), 200))
    )
    for dossier in session.scalars(stmt):
        oc = _outcome_bucket(dossier)
        if oc.get("closed"):
            skipped.append(dossier.id)
            continue
        pos = find_linked_position(session, dossier)
        if pos is None or pos.status != "CLOSED":
            skipped.append(dossier.id)
            continue
        record_outcome_from_position(session, dossier, pos)
        updated.append(dossier.id)
    session.flush()
    return {
        "schema": "ichivol.eve.outcome_sync.v1",
        "updated": updated,
        "skipped_count": len(skipped),
        "updated_count": len(updated),
        "note": "Outcomes never rewrite decision_time_json",
    }


def followup_summary(session: Session, dossier_id: str) -> dict[str, Any]:
    dossier = get_dossier(session, dossier_id)
    if dossier is None:
        return {"ok": False, "error": "dossier_not_found"}
    oc = _outcome_bucket(dossier)
    pos = find_linked_position(session, dossier)
    return {
        "ok": True,
        "dossier_id": dossier_id,
        "symbol": dossier.symbol,
        "execution_status": dossier.execution_status,
        "outcome": oc,
        "position": _position_snapshot(pos) if pos else None,
        "decision_time": dossier.decision_time_json,
        "timeline": build_dossier_timeline(dossier),
        "note": "decision_time is immutable; outcome is separate",
    }
