"""V2 — Eve verdict → Risk Kernel → portefeuilles virtuels.

Sans ``portfolio_code`` la soumission couvre **tous** les portefeuilles paper actifs (essai à blanc par défaut).
En autonomie, c'est ``eve.autopilot`` qui exécute, livre par livre, seulement là où le moteur a proposé un trade.

``execute`` n'est jamais implicite : sans ``execute=True`` explicite, rien n'est ouvert ni fermé (essai à blanc),
et ``execute=True`` est ignoré quand l'autonomie est coupée. Jamais de broker live.
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
from app.paper.portfolio import (
    RetiredPortfolioError,
    ensure_main_portfolio,
    resolve_trading_portfolio,
)
from app.paper.risk_kernel import (
    OpenPlan,
    PortfolioState,
    evaluate as risk_kernel_evaluate,
    market_state_from_profile,
    open_lots_from_positions,
)
from app.paper.strategy_profiles import MAIN_CODE

logger = logging.getLogger(__name__)

AUTONOMY_ENV = "EVE_PAPER_AUTONOMY"
ALL_VIRTUAL = "ALL"


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


def virtual_portfolio_codes(session: Session) -> list[str]:
    """Le compte paper visé par « tous les portefeuilles » : le portefeuille unique (2026-10-27).

    Les anciens comptes encore en base (avant le script de suppression) ne sont jamais visés."""
    ensure_main_portfolio(session)
    return [MAIN_CODE]


def _aggregate_portfolio_results(results: list[dict[str, Any]]) -> str:
    """Statut dossier après soumission multi-portefeuilles."""
    if not results:
        return "no_portfolios"
    statuses = [str(r.get("status") or "") for r in results]
    if any(s == "opened" for s in statuses):
        return "opened" if statuses.count("opened") == 1 else "opened_all_books"
    if any(s == "closed" for s in statuses):
        return "closed" if statuses.count("closed") == 1 else "closed_all_books"
    if any(s == "already_open" for s in statuses):
        return "already_open"
    if any(s == "dry_run_autonomy_off" for s in statuses):
        return "dry_run_autonomy_off"
    if any(s == "dry_run_close" for s in statuses):
        return "dry_run_close"
    if all(s.startswith("skipped_") or s in ("close_no_position", "skipped_symbol") for s in statuses):
        return statuses[0] if len(set(statuses)) == 1 else "skipped_all_books"
    if any(s == "risk_kernel_refused" for s in statuses):
        return "risk_kernel_refused"
    return statuses[-1] or "submitted_all_books"


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
    """Compte unique par défaut ; un code retiré n'est jamais tradé (None → ``unknown_portfolio``)."""
    try:
        return resolve_trading_portfolio(session, portfolio_code)
    except RetiredPortfolioError:
        return None


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
    portfolio_code: str | None = None,
    price: float | None = None,
    stop_distance: float | None = None,
    execute: bool | None = None,
    allow_screener: bool = True,
    action_override: str | None = None,
) -> dict[str, Any]:
    """Soumet (ou dry-run) le verdict Ève via Risk Kernel / close.

    ``portfolio_code=None`` ou ``ALL`` → **tous** les portefeuilles virtuels actifs.
    Un code précis → un seul livre.

    ``execute`` défaut = essai à blanc ; ``True`` n'agit qu'avec l'autonomie. HOLD/ABSTAIN n'ouvrent pas.
    """
    code = (portfolio_code or "").strip()
    if not code or code.upper() == ALL_VIRTUAL:
        return _submit_all_virtual_portfolios(
            session,
            dossier_id,
            price=price,
            stop_distance=stop_distance,
            execute=execute,
            allow_screener=allow_screener,
            action_override=action_override,
        )
    return _submit_one_portfolio(
        session,
        dossier_id,
        portfolio_code=code,
        price=price,
        stop_distance=stop_distance,
        execute=execute,
        allow_screener=allow_screener,
        action_override=action_override,
    )


def _submit_all_virtual_portfolios(
    session: Session,
    dossier_id: str,
    *,
    price: float | None = None,
    stop_distance: float | None = None,
    execute: bool | None = None,
    allow_screener: bool = True,
    action_override: str | None = None,
) -> dict[str, Any]:
    """Ève sur chaque portefeuille virtuel actif."""
    dossier = get_dossier(session, dossier_id)
    if dossier is None:
        return {"ok": False, "error": "dossier_not_found", "dossier_id": dossier_id}

    codes = virtual_portfolio_codes(session)
    per_book: list[dict[str, Any]] = []
    for code in codes:
        one = _submit_one_portfolio(
            session,
            dossier_id,
            portfolio_code=code,
            price=price,
            stop_distance=stop_distance,
            execute=execute,
            allow_screener=allow_screener,
            action_override=action_override,
        )
        per_book.append(one)

    now = datetime.now(timezone.utc).isoformat()
    agg_status = _aggregate_portfolio_results(per_book)
    executed_any = any(bool(r.get("executed")) for r in per_book)
    ok_any = any(bool(r.get("ok")) for r in per_book)
    auto = autonomy_enabled()

    dossier = get_dossier(session, dossier_id)
    verdict = None
    if dossier is not None:
        verdict = get_verdict(session, dossier.verdict_id) if dossier.verdict_id else None
        dossier.execution_status = agg_status
        _patch_verdict(
            verdict,
            paper_submit_at=now,
            status=agg_status,
            autonomy_enabled=auto,
            portfolios=[
                {
                    "portfolio_code": r.get("portfolio_code"),
                    "status": r.get("status"),
                    "executed": r.get("executed"),
                    "position_id": r.get("position_id"),
                    "risk_authorization": r.get("risk_authorization"),
                }
                for r in per_book
            ],
            executed=executed_any,
            order_submitted=any(bool(r.get("order_submitted")) for r in per_book),
        )
        if executed_any and verdict is not None:
            verdict.status = "authorized"
        session.flush()

    return {
        "schema": "ichivol.eve.paper_submit.v1",
        "dossier_id": dossier_id,
        "symbol": dossier.symbol if dossier else None,
        "timeframe": dossier.timeframe if dossier else None,
        "portfolio_code": ALL_VIRTUAL,
        "portfolios": per_book,
        "portfolio_codes": codes,
        "autonomy_enabled": auto,
        "ok": ok_any,
        "status": agg_status,
        "executed": executed_any,
        "order_submitted": any(bool(r.get("order_submitted")) for r in per_book),
        "evaluated_at": now,
        "note": "Ève → tous les portefeuilles virtuels actifs",
    }


def submit_to_portfolio(
    session: Session,
    dossier_id: str,
    *,
    portfolio_code: str,
    price: float | None = None,
    stop_distance: float | None = None,
    execute: bool | None = None,
    action_override: str | None = None,
    decided_by: str = "eve",
) -> dict[str, Any]:
    """One book only (used by ``eve.autopilot`` on the book whose engine method proposed the trade).

    ``decided_by="engine_over_eve"``: the engine trades although Ève refused. JEV degradation and the entry gate
    judge Ève's own trades, so they are skipped; the Risk Kernel still applies."""
    return _submit_one_portfolio(
        session,
        dossier_id,
        portfolio_code=portfolio_code,
        price=price,
        stop_distance=stop_distance,
        execute=execute,
        allow_screener=True,
        action_override=action_override,
        decided_by=decided_by,
    )


def _restore_status(fn):  # noqa: ANN001, ANN202 -- private decorator
    """Over Ève, put the dossier's execution status back once the engine's trade is submitted."""

    def wrapper(session: Session, dossier_id: str, **kw: Any) -> dict[str, Any]:
        if kw.get("decided_by") != "engine_over_eve":
            return fn(session, dossier_id, **kw)
        dossier = get_dossier(session, dossier_id)
        before = dossier.execution_status if dossier is not None else None
        try:
            return fn(session, dossier_id, **kw)
        finally:
            if dossier is not None:
                dossier.execution_status = before
                session.flush()

    return wrapper


@_restore_status
def _submit_one_portfolio(
    session: Session,
    dossier_id: str,
    *,
    portfolio_code: str,
    price: float | None = None,
    stop_distance: float | None = None,
    execute: bool | None = None,
    allow_screener: bool = True,
    action_override: str | None = None,
    decided_by: str = "eve",
) -> dict[str, Any]:
    """Soumet sur un seul portefeuille virtuel."""
    engine_over_eve = decided_by == "engine_over_eve"
    dossier = get_dossier(session, dossier_id)
    if dossier is None:
        return {"ok": False, "error": "dossier_not_found", "dossier_id": dossier_id}

    verdict = get_verdict(session, dossier.verdict_id) if dossier.verdict_id else None
    action = normalize_action(
        action_override
        or ((verdict.action if verdict else None) or dossier.eve_action)
    ) or "ABSTAIN"
    if engine_over_eve:
        # The trade is the engine's: Ève's verdict and dossier status keep describing her own answer.
        verdict = None

    auto = autonomy_enabled()
    # Never implicit: only an explicit execute=True acts, and only with autonomy on.
    do_execute = bool(execute)
    # Hard gate: never execute when autonomy is off.
    if do_execute and not auto:
        do_execute = False

    # Degradation ladder from decision_time — never open on late / low conf / jev_down.
    raw_dt = getattr(dossier, "decision_time_json", None)
    dt = raw_dt if isinstance(raw_dt, dict) else {}
    deg = dt.get("degradation") if isinstance(dt.get("degradation"), dict) else {}
    deg_level = str(deg.get("level") or "healthy")
    if engine_over_eve:
        deg_level = "healthy"
    if do_execute and action in ("LONG", "SHORT", "CLOSE") and deg_level in (
        "late",
        "low_confidence",
        "jev_down",
    ):
        do_execute = False

    gate = dt.get("entry_gate") if isinstance(dt.get("entry_gate"), dict) else {}
    gate_reject = (
        not engine_over_eve
        and action in ("LONG", "SHORT")
        and gate.get("decision") == "reject"
        and not gate.get("allowed", False)
    )
    if do_execute and gate_reject:
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
        "degradation": deg or None,
        "entry_gate": gate or None,
        "risk_authorization": "not_submitted",
        "order_submitted": False,
        "executed": False,
        "position_id": None,
        "evaluated_at": now,
        "decided_by": decided_by,
        "note": "V2 — Risk Kernel authority; no live trading",
    }
    if gate_reject:
        result["status"] = "gate_rejected"
        result["risk_authorization"] = "gate_rejected"
        result["ok"] = True
        result["note"] = (
            f"V2 — entry gate reject ({gate.get('reason')}); "
            "Risk Kernel not authorized to open"
        )
        dossier.execution_status = "gate_rejected"
        _patch_verdict(
            verdict,
            risk_authorization="gate_rejected",
            paper_submit_at=now,
            status="gate_rejected",
            entry_gate=gate,
        )
        session.flush()
        return result
    if deg_level in ("late", "low_confidence", "jev_down"):
        result["note"] = (
            f"V2 — degradation={deg_level}; execute forced off "
            f"(autonomy={'on' if auto else 'off'})"
        )

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

    # Livre dédié (ex. futures/crypto) : pas d'ouverture hors de son univers.
    # CLOSE reste possible s'il y a déjà une position sur ce livre.
    profile = getattr(portfolio, "strategy_profile", None) or {}
    symbol_ok = paper_engine.trades_symbol(profile if isinstance(profile, dict) else {}, dossier.symbol)
    if action in ("LONG", "SHORT") and not symbol_ok:
        result["ok"] = True
        result["status"] = "skipped_symbol"
        result["risk_authorization"] = "not_applicable"
        result["note"] = f"{portfolio_code} ne trade pas {dossier.symbol}"
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
        user_id="engine_over_eve" if engine_over_eve else "eve_intelligence",
        price=float(px),
        pipeline=pipeline,
        stop_distance=float(stop) if stop is not None else None,
        # Over Ève, the lot is the engine's: no eve_dossier_id, so Ève's follow-up never manages it.
        signal_extra=(
            {
                "decided_by": "engine_over_eve",
                "refused_by_eve_dossier_id": dossier_id,
                "eve_action": dossier.eve_action,
                "risk_kernel": rk,
            }
            if engine_over_eve
            else {
                "eve_dossier_id": dossier_id,
                "eve_action": action,
                "eve_paper_autonomy": True,
                "risk_kernel": rk,
            }
        ),
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
