"""V2 — Eve potential verdict → Risk Kernel → existing paper portfolios.

Autonomy is OFF by default (``EVE_PAPER_AUTONOMY=false``). When off, Risk Kernel
is still evaluated (dry-run) and recorded on the dossier; no position is opened
or closed.

Constraints:
- No Eve-specific portfolio — reuse baseline / existing strategy profiles only.
- Never real trading / live broker.
- Risk Kernel remains the sole open authority (Guardian advisory only).
- CLOSE uses existing ``close_manually`` (not Risk Kernel opens).
"""

from __future__ import annotations

import logging
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

logger = logging.getLogger(__name__)

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


def resolve_market_inputs(
    dossier,
    *,
    price: float | None = None,
    stop_distance: float | None = None,
    allow_screener: bool = True,
) -> tuple[float | None, float | None, str | None]:
    """Resolve price/stop: explicit → dossier facts → live screener.

    Returns ``(price, stop, source)`` where source is one of
    ``explicit`` / ``dossier`` / ``screener`` / ``partial`` / None.
    """
    ctx_price, ctx_stop = _market_inputs_from_dossier(dossier)
    px = price if price is not None else ctx_price
    stop = stop_distance if stop_distance is not None else ctx_stop
    source: str | None = None
    if price is not None:
        source = "explicit"
    elif ctx_price is not None:
        source = "dossier"

    if (px is None or px <= 0 or stop is None) and allow_screener:
        try:
            from app.screener.service import scan_symbol

            row = scan_symbol(str(dossier.symbol).upper(), timeframe=str(dossier.timeframe or "1h"))
            if px is None or px <= 0:
                live = getattr(row, "price", None)
                if isinstance(live, (int, float)) and live > 0:
                    px = float(live)
                    source = "screener" if source is None else f"{source}+screener"
            if stop is None and getattr(row, "atr", None) is not None:
                sug = getattr(row.atr, "suggested_stop_distance", None)
                if isinstance(sug, (int, float)) and sug > 0:
                    stop = float(sug)
                    source = (source or "screener") if "screener" in (source or "") else f"{source or 'dossier'}+screener_stop"
        except Exception as exc:  # noqa: BLE001 — dry-run must survive market data gaps
            logger.info("eve paper_submit screener unavailable: %s", type(exc).__name__)

    if px is not None and px > 0 and stop is not None:
        return px, stop, source or "resolved"
    if px is not None and px > 0:
        return px, stop, source or "partial"
    return px, stop, source


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


def _find_open_position(session: Session, *, symbol: str, portfolio_id: str):
    opens = paper_gates.open_positions(session, portfolio_id)
    for pos in opens:
        if str(getattr(pos, "symbol", "")).upper() == symbol.upper():
            return pos
    return None


def _patch_verdict(verdict, **fields: Any) -> None:
    if verdict is None:
        return
    body = dict(verdict.body_json or {})
    body.update(fields)
    verdict.body_json = body


def submit_paper_from_dossier(
    session: Session,
    dossier_id: str,
    *,
    portfolio_code: str = BASELINE_CODE,
    price: float | None = None,
    stop_distance: float | None = None,
    execute: bool | None = None,
    allow_screener: bool = True,
    action_override: str | None = None,
) -> dict[str, Any]:
    """Submit (or dry-run) an Eve potential verdict via Risk Kernel / close path.

    ``execute`` defaults to ``autonomy_enabled()``. HOLD/ABSTAIN never open.
    CLOSE closes an existing open lot when autonomy is on; otherwise dry-runs.
    LONG/SHORT go through Risk Kernel then ``open_user_confirmed``.
    ``action_override`` lets Phase J follow-up submit CLOSE without mutating
    the original strategic verdict permanently.
    """
    dossier = get_dossier(session, dossier_id)
    if dossier is None:
        return {"ok": False, "error": "dossier_not_found", "dossier_id": dossier_id}

    verdict = get_verdict(session, dossier.verdict_id) if dossier.verdict_id else None
    action = normalize_action(
        action_override
        or ((verdict.action if verdict else None) or dossier.eve_action)
    ) or "ABSTAIN"

    auto = autonomy_enabled()
    do_execute = auto if execute is None else bool(execute)
    # Hard gate: never execute when autonomy is off.
    if do_execute and not auto:
        do_execute = False

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
        "note": "V2 — Risk Kernel authority; no live trading",
    }

    if action == "ABSTAIN":
        result["ok"] = True
        result["status"] = "skipped_abstain"
        result["risk_authorization"] = "not_applicable"
        dossier.execution_status = "skipped_abstain"
        _patch_verdict(verdict, risk_authorization="not_applicable", paper_submit_at=now, status="skipped_abstain")
        session.flush()
        return result

    if action == "HOLD":
        result["ok"] = True
        result["status"] = "skipped_hold"
        result["risk_authorization"] = "not_applicable"
        result["note"] = "HOLD = maintain; no Risk Kernel open/close"
        dossier.execution_status = "skipped_hold"
        _patch_verdict(verdict, risk_authorization="not_applicable", paper_submit_at=now, status="skipped_hold")
        session.flush()
        return result

    portfolio = _resolve_portfolio(session, portfolio_code)
    if portfolio is None:
        result["ok"] = False
        result["error"] = "unknown_portfolio"
        result["status"] = "refused"
        return result

    px, stop, mkt_source = resolve_market_inputs(
        dossier, price=price, stop_distance=stop_distance, allow_screener=allow_screener
    )
    result["market_source"] = mkt_source

    # —— CLOSE ——
    if action == "CLOSE":
        open_pos = _find_open_position(session, symbol=dossier.symbol, portfolio_id=portfolio.id)
        result["open_position_id"] = open_pos.id if open_pos is not None else None
        if open_pos is None:
            result["ok"] = True
            result["status"] = "close_no_position"
            result["risk_authorization"] = "not_applicable"
            dossier.execution_status = "close_no_position"
            _patch_verdict(verdict, paper_submit_at=now, status="close_no_position")
            session.flush()
            return result
        if px is None or px <= 0:
            result["ok"] = False
            result["error"] = "missing_price"
            result["status"] = "refused"
            result["hint"] = "Pass price= or ensure screener/dossier price for CLOSE"
            return result
        result["price"] = float(px)
        result["risk_authorization"] = "close_authorized_dry_run" if not do_execute else "close_authorized"
        if not do_execute:
            result["ok"] = True
            result["status"] = "dry_run_close"
            result["would_close_position_id"] = open_pos.id
            dossier.execution_status = "dry_run_close"
            _patch_verdict(
                verdict,
                risk_authorization="close_authorized_dry_run",
                paper_submit_at=now,
                would_close_position_id=open_pos.id,
                autonomy_enabled=auto,
            )
            session.flush()
            return result
        closed = paper_engine.close_manually(session, open_pos.id, price=float(px))
        if closed is None:
            result["ok"] = True
            result["status"] = "close_refused"
            dossier.execution_status = "close_refused"
            session.flush()
            return result
        result["ok"] = True
        result["status"] = "closed"
        result["order_submitted"] = True
        result["executed"] = True
        result["position_id"] = closed.id
        dossier.execution_status = "closed"
        _patch_verdict(
            verdict,
            risk_authorization="close_authorized",
            order_submitted=True,
            executed=True,
            position_id=closed.id,
            paper_submit_at=now,
        )
        if verdict is not None:
            verdict.status = "authorized"
        session.flush()
        return result

    # —— LONG / SHORT ——
    if action not in ("LONG", "SHORT"):
        result["ok"] = True
        result["status"] = "skipped_non_directional"
        result["risk_authorization"] = "not_applicable"
        dossier.execution_status = "skipped_non_directional"
        session.flush()
        return result

    if px is None or px <= 0:
        result["ok"] = False
        result["error"] = "missing_price"
        result["status"] = "refused"
        result["hint"] = "Pass price= or ensure context/screener price"
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
        _patch_verdict(verdict, risk_authorization="refused", risk_kernel=rk, paper_submit_at=now)
        session.flush()
        return result

    result["risk_authorization"] = "accepted_dry_run" if not do_execute else "accepted"

    if not do_execute:
        result["ok"] = True
        result["status"] = "dry_run_autonomy_off"
        result["order_submitted"] = False
        dossier.execution_status = "dry_run_autonomy_off"
        _patch_verdict(
            verdict,
            risk_authorization="accepted_dry_run",
            risk_kernel=rk,
            paper_submit_at=now,
            autonomy_enabled=auto,
        )
        session.flush()
        return result

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
    _patch_verdict(
        verdict,
        risk_authorization="accepted",
        order_submitted=True,
        executed=True,
        position_id=position.id,
        risk_kernel=rk,
        paper_submit_at=now,
    )
    if verdict is not None:
        verdict.status = "authorized"
    session.flush()
    return result
