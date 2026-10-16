"""V2 scaffold — Eve potential verdict → Risk Kernel → existing paper portfolios.

Autonomy is OFF by default (``EVE_PAPER_AUTONOMY=false``). When off, Risk Kernel
is still evaluated (dry-run) and recorded on the dossier; no position is opened.

Constraints:
- No Eve-specific portfolio — reuse baseline / existing strategy profiles only.
- Never real trading / live broker.
- Risk Kernel remains the sole open authority (Guardian advisory only).
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.agents.types import Direction
from app.decision.pipeline import PipelineResult, PipelineStage, StageId, StageStatus
from app.eve.actions import normalize_action
from app.eve.dossier import get_dossier, get_verdict
from app.paper import broker as paper_broker
from app.paper import engine as paper_engine
from app.paper import gates as paper_gates
from app.paper.portfolio import ensure_baseline_portfolio, ensure_portfolio, get_portfolio_by_code
from app.paper.risk_kernel import (
    OpenPlan,
    PortfolioState,
    evaluate as risk_kernel_evaluate,
    market_state_from_profile,
    open_lots_from_positions,
)
from app.paper.strategy_profiles import BASELINE_CODE, syncable_profile_codes

AUTONOMY_ENV = "EVE_PAPER_AUTONOMY"


def autonomy_enabled() -> bool:
    """Prefer Settings when available; env override still wins for ops toggles."""
    env = os.getenv(AUTONOMY_ENV)
    if env is not None and env != "":
        return env.lower() in ("1", "true", "yes", "on")
    try:
        from app.config import settings

        return bool(settings.eve_paper_autonomy)
    except Exception:
        return False


def _action_to_pipeline(action: str) -> PipelineResult | None:
    """Map Eve LONG/SHORT to a minimal BUY/SELL PipelineResult for open_user_confirmed."""
    if action == "LONG":
        decision, direction = "BUY", Direction.LONG
    elif action == "SHORT":
        decision, direction = "SELL", Direction.SHORT
    else:
        return None
    stage = PipelineStage(
        StageId.DIRECTION,
        StageStatus.PASS,
        f"eve_v2:{action}",
        ["eve_paper_submit"],
    )
    return PipelineResult(
        decision=decision,
        direction=direction,
        stages=[stage],
    )


def _resolve_portfolio(session: Session, portfolio_code: str):
    if portfolio_code == BASELINE_CODE:
        return ensure_baseline_portfolio(session)
    if portfolio_code in syncable_profile_codes():
        return ensure_portfolio(session, portfolio_code)
    return get_portfolio_by_code(session, portfolio_code)


def _market_inputs_from_dossier(dossier) -> tuple[float | None, float | None]:
    """Best-effort price / stop_distance from persisted context facts."""
    ctx = dossier.context_json or {}
    price: float | None = None
    stop: float | None = None
    for fact in ctx.get("facts") or []:
        if not isinstance(fact, dict):
            continue
        field = str(fact.get("field") or "")
        fid = str(fact.get("id") or "")
        val = fact.get("value")
        if price is None and isinstance(val, (int, float)):
            if field in ("price", "last", "close") or "price" in fid.lower():
                price = float(val)
        if stop is None and isinstance(val, (int, float)):
            if "stop" in field.lower() or "atr" in field.lower() or "stop" in fid.lower():
                if float(val) > 0:
                    stop = float(val)
    engines = ctx.get("engines") or {}
    for eng_facts in engines.values():
        if not isinstance(eng_facts, list):
            continue
        for item in eng_facts:
            if not isinstance(item, dict):
                continue
            field = str(item.get("field") or "")
            val = item.get("value")
            if price is None and field in ("price", "last", "close") and isinstance(val, (int, float)):
                price = float(val)
            if stop is None and ("stop" in field or "atr" in field) and isinstance(val, (int, float)):
                if float(val) > 0:
                    stop = float(val)
    return price, stop


def evaluate_risk_kernel_for_plan(
    session: Session,
    *,
    symbol: str,
    timeframe: str,
    direction: str,
    price: float,
    stop_distance: float | None,
    portfolio,
) -> dict[str, Any]:
    """Pure Risk Kernel evaluation against an existing portfolio (no open)."""
    profile = portfolio.strategy_profile or {}
    equity = paper_broker.estimate_equity(session, portfolio)
    opens = paper_gates.open_positions(session, portfolio.id)
    rk = risk_kernel_evaluate(
        OpenPlan(
            symbol=symbol,
            timeframe=timeframe,
            direction=direction,
            price=price,
            stop_distance=stop_distance,
            stale=False,
        ),
        PortfolioState(
            cash=float(portfolio.cash),
            equity=float(equity),
            profile=profile,
            open_positions=open_lots_from_positions(opens),
            day_start_equity=paper_gates.day_start_equity(session, portfolio),
            traded_run_id=None,
            kill_switch_armed=bool(getattr(portfolio, "kill_switch_armed", False)),
            daily_loss_locked=bool(getattr(portfolio, "daily_loss_locked", False)),
        ),
        market_state_from_profile(profile, symbol),
        apply_gates=paper_gates.has_gates(profile),
        check_size=True,
    )
    return rk.to_dict()


def submit_paper_from_dossier(
    session: Session,
    dossier_id: str,
    *,
    portfolio_code: str = BASELINE_CODE,
    price: float | None = None,
    stop_distance: float | None = None,
    execute: bool | None = None,
) -> dict[str, Any]:
    """Submit (or dry-run) an Eve potential verdict via Risk Kernel.

    ``execute`` defaults to ``autonomy_enabled()``. Even when True, HOLD/CLOSE/
    ABSTAIN never open; only LONG/SHORT are candidates.
    """
    dossier = get_dossier(session, dossier_id)
    if dossier is None:
        return {"ok": False, "error": "dossier_not_found", "dossier_id": dossier_id}

    verdict = get_verdict(session, dossier.verdict_id) if dossier.verdict_id else None
    action = normalize_action(
        (verdict.action if verdict else None) or dossier.eve_action
    ) or "ABSTAIN"

    auto = autonomy_enabled()
    do_execute = auto if execute is None else bool(execute)

    now = datetime.now(timezone.utc).isoformat()
    result: dict[str, Any] = {
        "schema": "ichivol.eve.paper_submit.v1",
        "dossier_id": dossier_id,
        "symbol": dossier.symbol,
        "timeframe": dossier.timeframe,
        "eve_action": action,
        "portfolio_code": portfolio_code,
        "autonomy_enabled": auto,
        "execute_requested": do_execute,
        "risk_authorization": "not_submitted",
        "order_submitted": False,
        "executed": False,
        "position_id": None,
        "evaluated_at": now,
        "note": "V2 scaffold — Risk Kernel authority; no live trading",
    }

    if action not in ("LONG", "SHORT"):
        result["ok"] = True
        result["status"] = "skipped_non_directional"
        result["risk_authorization"] = "not_applicable"
        dossier.execution_status = "skipped_non_directional"
        session.flush()
        return result

    portfolio = _resolve_portfolio(session, portfolio_code)
    if portfolio is None:
        result["ok"] = False
        result["error"] = "unknown_portfolio"
        result["status"] = "refused"
        return result

    ctx_price, ctx_stop = _market_inputs_from_dossier(dossier)
    px = price if price is not None else ctx_price
    stop = stop_distance if stop_distance is not None else ctx_stop
    if px is None or px <= 0:
        result["ok"] = False
        result["error"] = "missing_price"
        result["status"] = "refused"
        result["hint"] = "Pass price= or ensure context facts include price"
        return result

    rk = evaluate_risk_kernel_for_plan(
        session,
        symbol=dossier.symbol,
        timeframe=dossier.timeframe,
        direction=action,
        price=float(px),
        stop_distance=float(stop) if stop is not None else None,
        portfolio=portfolio,
    )
    result["risk_kernel"] = rk
    result["price"] = float(px)
    result["stop_distance"] = float(stop) if stop is not None else None

    if not rk.get("accepted"):
        result["ok"] = True
        result["status"] = "risk_kernel_refused"
        result["risk_authorization"] = "refused"
        dossier.execution_status = "risk_kernel_refused"
        if verdict is not None:
            body = dict(verdict.body_json or {})
            body["risk_authorization"] = "refused"
            body["risk_kernel"] = rk
            body["paper_submit_at"] = now
            verdict.body_json = body
        session.flush()
        return result

    result["risk_authorization"] = "accepted_dry_run" if not do_execute else "accepted"

    if not do_execute:
        result["ok"] = True
        result["status"] = "dry_run_autonomy_off"
        result["order_submitted"] = False
        dossier.execution_status = "dry_run_autonomy_off"
        if verdict is not None:
            body = dict(verdict.body_json or {})
            body["risk_authorization"] = "accepted_dry_run"
            body["risk_kernel"] = rk
            body["paper_submit_at"] = now
            body["autonomy_enabled"] = auto
            verdict.body_json = body
        session.flush()
        return result

    # Autonomy ON — open through existing paper path (user_confirmed source).
    pipeline = _action_to_pipeline(action)
    assert pipeline is not None

    position, created = paper_engine.open_user_confirmed(
        session,
        symbol=dossier.symbol,
        timeframe=dossier.timeframe,
        user_id="eve_intelligence",
        price=float(px),
        pipeline=pipeline,
        stop_distance=float(stop) if stop is not None else None,
        signal_extra={
            "eve_dossier_id": dossier_id,
            "eve_action": action,
            "eve_paper_autonomy": True,
            "risk_kernel": rk,
        },
        portfolio=portfolio,
    )

    if position is None:
        result["ok"] = True
        result["status"] = "open_refused"
        result["risk_authorization"] = "accepted_but_open_failed"
        result["order_submitted"] = True
        dossier.execution_status = "open_refused"
        session.flush()
        return result

    result["ok"] = True
    result["status"] = "opened" if created else "already_open"
    result["order_submitted"] = True
    result["executed"] = True
    result["position_id"] = position.id
    result["created"] = created
    dossier.execution_status = "opened" if created else "already_open"
    if verdict is not None:
        body = dict(verdict.body_json or {})
        body["risk_authorization"] = "accepted"
        body["order_submitted"] = True
        body["executed"] = True
        body["position_id"] = position.id
        body["risk_kernel"] = rk
        body["paper_submit_at"] = now
        verdict.body_json = body
        verdict.status = "authorized"
    session.flush()
    return result
