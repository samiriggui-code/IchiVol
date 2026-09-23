"""Paper trading — preview, propose, open, close (after shadow routes)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from sqlalchemy.orm import Session

from app.api.common import (
    _atr_params_override,
    _paper_position_dict,
    _rvol_params_override,
)
from app.config import settings
from app.db.session import SessionLocal
from app.decision.pipeline import PipelineResult
from app.paper import broker as paper_broker
from app.paper import engine as paper_engine
from app.paper import gates as paper_gates
from app.paper.portfolio import ensure_baseline_portfolio
from app.screener.service import scan_symbol

router_after_shadow = APIRouter(prefix=settings.engine_api_prefix, tags=["engine"])


def _open_refusal_detail(
    session: Session,
    *,
    pipeline: PipelineResult,
    stop_distance: float | None,
    symbol: str,
    timeframe: str,
    price: float,
) -> str:
    """Honest 422 detail when open_user_confirmed returns None.

    WATCH/NO_TRADE stay as ``not_actionable``; gates / short / sizing get their
    real reason codes (``no_atr_stop``, ``short_not_allowed``, …).
    """
    decision = pipeline.decision
    if decision in ("WATCH", "NO_TRADE"):
        return "not_actionable: pipeline.decision is WATCH/NO_TRADE, nothing to open"
    direction = "LONG" if decision == "BUY" else ("SHORT" if decision == "SELL" else None)
    if direction is None:
        return "not_actionable: pipeline.decision is WATCH/NO_TRADE, nothing to open"

    portfolio = ensure_baseline_portfolio(session)
    profile = portfolio.strategy_profile or {}
    if direction == "SHORT" and profile.get("allow_short", True) is False:
        return "short_not_allowed: baseline portfolio does not allow short selling"
    if paper_gates.has_gates(profile):
        reason = paper_gates.entry_gate(
            session,
            portfolio,
            symbol=symbol,
            timeframe=timeframe,
            price=price,
            stop_distance=stop_distance,
            equity=paper_broker.estimate_equity(session, portfolio),
        )
        if reason is not None:
            return f"{reason}: entry gate refused open"
    if not stop_distance or stop_distance <= 0:
        return "no_atr_stop: ATR stop required, nothing to open"
    return "open_refused: insufficient_cash_or_size or max_positions"


@router_after_shadow.get("/paper/preview")
def preview_manual_paper_buy(
    symbol: str,
    notional: float,
    timeframe: str = "1h",
    stop_pct: float | None = None,
    take_profit_r: float | None = None,
    portfolio_code: str = "ICHIVOL_BASELINE_V1",
) -> dict:
    """What a user-chosen buy would cost, risk and do to the portfolio. Read-only, never opens anything."""
    from app.paper.manual import preview_manual_buy
    from app.paper.scenarios import build_scenarios

    try:
        row = scan_symbol(symbol.upper(), timeframe=timeframe)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    session = SessionLocal()
    try:
        preview = preview_manual_buy(
            session, row, notional=notional, stop_pct=stop_pct, take_profit_r=take_profit_r, portfolio_code=portfolio_code
        )
        # T0-CALC: scenarios block is additive — existing preview fields untouched.
        try:
            from app.paper.manual import paper_broker_get_portfolio

            portfolio = paper_broker_get_portfolio(session, portfolio_code)
            profile = portfolio.strategy_profile or {}
            order = preview["order"]
            outcomes = preview["outcomes"]
            preview["scenarios"] = build_scenarios(
                preview["symbol"],
                preview["timeframe"],
                float(order["entry_fill"]),
                float(order["qty"]),
                float(order["stop_price"]),
                float(order["take_profit_price"]),
                profile,
                net_gain_if_target=float(outcomes["net_gain_if_target"]),
                net_loss_if_stop=float(outcomes["net_loss_if_stop"]),
                invested=float(order["notional"]),
                equity=float(preview["portfolio"]["equity"]),
                entry_fee=float(preview["costs"]["commission_entry"]),
                direction=preview.get("direction") or "LONG",
            )
        except Exception:  # noqa: BLE001 — preview must still return without scenarios
            preview["scenarios"] = None
        return preview
    finally:
        session.close()


@router_after_shadow.get("/paper/positions/{position_id}/scenarios")
def paper_position_scenarios(position_id: str) -> dict:
    """Historical scenarios for an OPEN paper lot (from mark + from entry). Read-only."""
    from app.paper import financing as paper_financing
    from app.paper.broker import _profile, estimate_equity
    from app.paper.marks import resolve_marks
    from app.paper.scenarios import build_open_position_scenarios

    session = SessionLocal()
    try:
        position = paper_engine.get_position(session, position_id)
        if position is None:
            raise HTTPException(status_code=404, detail="position_not_found")
        if position.status != "OPEN":
            raise HTTPException(status_code=409, detail="position_not_open")
        if not position.qty or position.qty <= 0:
            raise HTTPException(status_code=422, detail="position_incomplete")

        from app.db.models import PaperPortfolio

        portfolio = session.get(PaperPortfolio, position.portfolio_id)
        if portfolio is None:
            raise HTTPException(status_code=404, detail="portfolio_not_found")

        marks = resolve_marks([position.symbol], timeframe=position.timeframe or "1h")
        mark = marks.get(position.symbol.upper())
        if mark is None or mark.source == "missing" or mark.price <= 0:
            raise HTTPException(status_code=422, detail="mark_unavailable")

        profile = _profile(portfolio)
        equity = estimate_equity(session, portfolio)
        paid = paper_financing.financing_total_for_position(session, position.id)
        return build_open_position_scenarios(
            position,
            mark_price=float(mark.price),
            profile=profile,
            equity=float(equity),
            financing_paid=float(paid),
        )
    finally:
        session.close()


@router_after_shadow.get("/paper/positions/{position_id}/proximity")
def paper_position_proximity(position_id: str, near_pct: float = 0.20) -> dict:
    """T0-NOTIF — remaining fraction to stop/target (same geometry as scenarios). Read-only."""
    from app.paper.marks import resolve_marks
    from app.paper.scenarios import compute_level_proximity

    if near_pct <= 0 or near_pct > 1:
        raise HTTPException(status_code=422, detail="near_pct must be in (0, 1]")

    session = SessionLocal()
    try:
        position = paper_engine.get_position(session, position_id)
        if position is None:
            raise HTTPException(status_code=404, detail="position_not_found")
        if position.status != "OPEN":
            raise HTTPException(status_code=409, detail="position_not_open")

        marks = resolve_marks(
            [position.symbol],
            timeframe=position.timeframe or "1h",
            allow_fetch=True,
            fetch_budget_s=1.5,
            block_on_provider=False,
        )
        mark = marks.get(position.symbol.upper())
        if mark is None or mark.source == "missing" or mark.price <= 0:
            raise HTTPException(status_code=422, detail="mark_unavailable")

        entry = float(position.entry_price)
        stop = (
            float(position.stop_price)
            if position.stop_price is not None
            else entry * 0.98
        )
        target = (
            float(position.take_profit_price)
            if position.take_profit_price is not None
            else entry * 1.04
        )
        prox = compute_level_proximity(
            entry=entry,
            mark=float(mark.price),
            stop=stop,
            target=target,
            near_pct=float(near_pct),
        )
        return {
            "position_id": position.id,
            "symbol": position.symbol,
            "timeframe": position.timeframe,
            "direction": position.direction,
            "user_id": position.user_id,
            "mark_source": mark.source,
            "proximity": prox,
        }
    finally:
        session.close()


@router_after_shadow.get("/paper/propose")
def propose_paper_trade(
    symbol: str,
    timeframe: str = "1h",
    portfolio_code: str = "ICHIVOL_BASELINE_V1",
    rvol_low: float | None = None,
    rvol_significant: float | None = None,
    rvol_strong: float | None = None,
    rvol_anomaly: float | None = None,
    atr_dead_percentile: float | None = None,
    atr_extreme_percentile: float | None = None,
    atr_stop_multiplier: float | None = None,
) -> dict:
    """Dry-run paper order intent (qty/stop/TP) — read-only, never opens a position.

    Front flow: propose → user confirms → POST /paper/positions.
    """
    from app.paper.intent import propose_order_intent

    rvol_params = _rvol_params_override(rvol_low, rvol_significant, rvol_strong, rvol_anomaly)
    atr_params = _atr_params_override(atr_dead_percentile, atr_extreme_percentile, atr_stop_multiplier)
    try:
        row = scan_symbol(
            symbol.upper(), timeframe=timeframe, rvol_params=rvol_params, atr_params=atr_params
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    session = SessionLocal()
    try:
        intent = propose_order_intent(session, row, portfolio_code=portfolio_code)
        return {
            "intent": intent.to_dict(),
            "pipeline": {
                "decision": row.pipeline.decision,
                "direction": row.pipeline.direction.value,
            },
        }
    finally:
        session.close()


@router_after_shadow.post("/paper/positions")
def open_paper_position(
    symbol: str,
    user_id: str,
    timeframe: str = "1h",
    rvol_low: float | None = None,
    rvol_significant: float | None = None,
    rvol_strong: float | None = None,
    rvol_anomaly: float | None = None,
    atr_dead_percentile: float | None = None,
    atr_extreme_percentile: float | None = None,
    atr_stop_multiplier: float | None = None,
    discretionary: bool = False,
    notional: float | None = None,
    stop_pct: float | None = None,
    take_profit_r: float | None = None,
) -> dict:
    """Called by the server when a user hits "Confirmer" in the Journal --
    opens a virtual `user_confirmed` position at the current live
    price/decision, unless one is already open for this (symbol, timeframe,
    user_id) (idempotent) or the live decision isn't actionable right now.

    Same 7 optional RVOL/ATR threshold overrides as `/decisions/{symbol}` and
    `/screener` (previously missing here -- feature parity gap, not a new
    concept): lets a caller open a position under a deliberately-labeled
    demo/calibration threshold set instead of the engine defaults, using the
    exact same real market data and pipeline logic either way."""
    rvol_params = _rvol_params_override(rvol_low, rvol_significant, rvol_strong, rvol_anomaly)
    atr_params = _atr_params_override(atr_dead_percentile, atr_extreme_percentile, atr_stop_multiplier)
    try:
        row = scan_symbol(
            symbol.upper(), timeframe=timeframe, rvol_params=rvol_params, atr_params=atr_params
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    if (getattr(row, "signal_timing", None) or {}).get("stale"):
        raise HTTPException(
            status_code=422,
            detail="stale_data: provider candles are late/frozen, refusing to open on an outdated signal",
        )
    stop = row.atr.suggested_stop_distance if row.atr is not None else None
    manual_notional = None
    pipeline_for_open = row.pipeline
    extra_signal: dict = {}
    if discretionary:
        # Buy chosen by the user (any amount, own stop/target), no engine BUY required. Re-validated here with the
        # same numbers the preview showed; refusals are explained, never silent.
        from dataclasses import replace as _dc_replace

        from app.agents.types import Direction as _Dir
        from app.paper.manual import preview_manual_buy

        if notional is None:
            raise HTTPException(status_code=422, detail="bad_request: notional is required for a discretionary buy")
        _s = SessionLocal()
        try:
            prev = preview_manual_buy(_s, row, notional=notional, stop_pct=stop_pct, take_profit_r=take_profit_r)
        finally:
            _s.close()
        if not prev["ok"]:
            first = prev["blocking"][0]
            raise HTTPException(status_code=422, detail=f"{first['code']}: {first['message']}")
        manual_notional = notional
        stop = prev["inputs"]["stop_distance"]
        pipeline_for_open = _dc_replace(row.pipeline, decision="BUY", direction=_Dir.LONG)
        extra_signal = {"discretionary": True, "engine_verdict": row.pipeline.decision}
    session = SessionLocal()
    try:
        evidence_id = None
        if row.evidence is not None:
            from app.evidence.persistence import persist_evidence

            evidence_row = persist_evidence(
                session,
                report=row.evidence,
                decision=row.pipeline.decision,
                market_snapshot={
                    "price": row.price,
                    "volume_type": row.candles[-1].volume_type.value if row.candles else "NONE",
                },
            )
            evidence_id = evidence_row.id
            session.flush()

        position, created = paper_engine.open_user_confirmed(
            session,
            symbol=row.symbol,
            timeframe=timeframe,
            user_id=user_id,
            price=row.price,
            pipeline=pipeline_for_open,
            stop_distance=stop,
            evidence_id=evidence_id,
            signal_extra={
                "evidence_id": evidence_id,
                "context": row.context.to_dict() if row.context else None,
                **extra_signal,
            },
            manual_notional=manual_notional,
            take_profit_r=take_profit_r if discretionary else None,
        )
        if position is None:
            raise HTTPException(
                status_code=422,
                detail=_open_refusal_detail(
                    session,
                    pipeline=pipeline_for_open,
                    stop_distance=stop,
                    symbol=row.symbol,
                    timeframe=timeframe,
                    price=row.price,
                ),
            )
        if evidence_id and position.evidence_id is None:
            position.evidence_id = evidence_id
            session.commit()
        payload = _paper_position_dict(position)
        payload["created"] = created
        if not created:
            payload["already_open"] = True
        return payload
    finally:
        session.close()


@router_after_shadow.post("/paper/positions/{position_id}/close")
def close_paper_position(position_id: str) -> dict:
    """Manual close at the current live price for that position's own
    symbol/timeframe -- e.g. wired to archiving a Journal entry."""
    session = SessionLocal()
    try:
        existing = paper_engine.get_position(session, position_id)
        if existing is None:
            raise HTTPException(status_code=404, detail="position_not_found")
        if existing.status != "OPEN":
            raise HTTPException(status_code=409, detail="position_already_closed")
        symbol, timeframe = existing.symbol, existing.timeframe
    finally:
        session.close()

    try:
        row = scan_symbol(symbol, timeframe=timeframe)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    session = SessionLocal()
    try:
        closed = paper_engine.close_manually(session, position_id, price=row.price)
        if closed is None:
            raise HTTPException(status_code=409, detail="position_already_closed")
        return _paper_position_dict(closed)  # while the session is still open, see open_paper_position
    finally:
        session.close()
