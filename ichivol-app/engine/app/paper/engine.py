"""Paper trading -- virtual positions only.

Phase 1 PaperBroker: ATR sizing against portfolio capital.
Phase 2: multi-portfolio sync + optional Market Structure gates on
experimental profiles only. ICHIVOL_BASELINE_V1 never gains structure filters.
Never a real order.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import PaperPortfolio, PaperPosition
from app.decision.pipeline import PipelineResult
from app.context.gate import apply_context_gate
from app.fibonacci.gate import apply_fibonacci_gate
from app.paper import broker as paper_broker
from app.paper.portfolio import ensure_baseline_portfolio, ensure_syncable_portfolios
from app.shadow import broker as shadow_broker
from app.structure.gate import apply_structure_gate


def _direction_for(decision: str) -> str | None:
    if decision == "BUY":
        return "LONG"
    if decision == "SELL":
        return "SHORT"
    return None


def _signal_payload(pipeline: PipelineResult, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "decision": pipeline.decision,
        "direction": getattr(pipeline.direction, "value", str(pipeline.direction)),
        "stages": [
            {
                "id": getattr(getattr(s, "id", None), "value", getattr(s, "id", None)),
                "status": getattr(getattr(s, "status", None), "value", str(getattr(s, "status", ""))),
                "summary": getattr(s, "summary", None),
                "codes": getattr(s, "codes", None),
            }
            for s in (pipeline.stages or [])
        ],
    }
    if extra:
        payload.update(extra)
    return payload


def _get_open_position(
    session: Session,
    *,
    symbol: str,
    timeframe: str,
    source: str,
    user_id: str | None,
    portfolio_id: str | None = None,
) -> PaperPosition | None:
    stmt = select(PaperPosition).where(
        PaperPosition.symbol == symbol,
        PaperPosition.timeframe == timeframe,
        PaperPosition.source == source,
        PaperPosition.user_id == user_id,
        PaperPosition.status == "OPEN",
    )
    if portfolio_id is not None:
        stmt = stmt.where(PaperPosition.portfolio_id == portfolio_id)
    return session.execute(stmt).scalar_one_or_none()


def _close_legacy(position: PaperPosition, *, price: float, reason: str) -> None:
    position.status = "CLOSED"
    position.exit_time = datetime.now(timezone.utc)
    position.exit_price = price
    position.exit_reason = reason
    position.pnl_pct = (
        (price / position.entry_price) - 1.0
        if position.direction == "LONG"
        else (position.entry_price / price) - 1.0
    )


def _open_legacy(
    session: Session,
    *,
    symbol: str,
    timeframe: str,
    source: str,
    user_id: str | None,
    direction: str,
    price: float,
    decision: str,
    portfolio_id: str | None = None,
) -> PaperPosition:
    position = PaperPosition(
        portfolio_id=portfolio_id,
        symbol=symbol,
        timeframe=timeframe,
        source=source,
        user_id=user_id,
        direction=direction,
        status="OPEN",
        entry_time=datetime.now(timezone.utc),
        entry_price=price,
        entry_decision=decision,
    )
    session.add(position)
    return position


def sync_position(
    session: Session,
    *,
    symbol: str,
    timeframe: str,
    source: str,
    user_id: str | None,
    price: float,
    pipeline: PipelineResult,
    stop_distance: float | None = None,
    signal_extra: dict[str, Any] | None = None,
    portfolio: PaperPortfolio | None = None,
) -> PaperPosition | None:
    """One symbol open/hold/close for one portfolio. Capital sizing when stop set."""
    if portfolio is None:
        try:
            portfolio = ensure_baseline_portfolio(session)
        except Exception:
            portfolio = None

    portfolio_id = portfolio.id if portfolio is not None else None
    existing = _get_open_position(
        session,
        symbol=symbol,
        timeframe=timeframe,
        source=source,
        user_id=user_id,
        portfolio_id=portfolio_id,
    )
    direction = _direction_for(pipeline.decision)
    signal = _signal_payload(pipeline, signal_extra)

    if existing is not None:
        paper_broker.update_excursions(existing, price)
        stop_reason = paper_broker.check_stop_or_tp(existing, price)
        if stop_reason is not None:
            if existing.qty:
                paper_broker.close_capital_position(
                    session, existing, price=price, reason=stop_reason, signal=signal
                )
            else:
                _close_legacy(existing, price=price, reason=stop_reason)
            session.flush()
            return existing

        if direction == existing.direction:
            return None

        reason = "pipeline_flipped" if direction is not None else "pipeline_downgraded"
        if existing.qty:
            paper_broker.close_capital_position(
                session, existing, price=price, reason=reason, signal=signal
            )
        else:
            _close_legacy(existing, price=price, reason=reason)
        session.flush()
        return existing

    if direction is None:
        return None

    if portfolio is not None and stop_distance and stop_distance > 0:
        require_atr = bool((portfolio.strategy_profile or {}).get("require_atr_stop", True))
        position = paper_broker.open_capital_position(
            session,
            portfolio=portfolio,
            symbol=symbol,
            timeframe=timeframe,
            source=source,
            user_id=user_id,
            direction=direction,
            price=price,
            decision=pipeline.decision,
            stop_distance=stop_distance,
            signal=signal,
        )
        if position is not None:
            session.flush()
            return position
        if require_atr:
            return None

    position = _open_legacy(
        session,
        symbol=symbol,
        timeframe=timeframe,
        source=source,
        user_id=user_id,
        direction=direction,
        price=price,
        decision=pipeline.decision,
        portfolio_id=portfolio_id,
    )
    session.flush()
    return position


def sync_auto_watchlist(session: Session, rows: Sequence) -> list[PaperPosition]:
    """Reuse screener rows; size when ATR stop is present; sync all syncable portfolios."""
    try:
        portfolios = ensure_syncable_portfolios(session)
    except Exception:
        portfolios = []
        try:
            portfolios = [ensure_baseline_portfolio(session)]
        except Exception:
            portfolios = []

    marks: dict[str, float] = {}
    touched: list[PaperPosition] = []
    # Cache structure gate by (symbol,tf, detectors key) within this cycle
    gate_cache: dict[tuple[str, str, str], Any] = {}

    for row in rows:
        stop = None
        if getattr(row, "atr", None) is not None:
            stop = getattr(row.atr, "suggested_stop_distance", None)
        rvol_val = None
        rvol_out = getattr(row, "rvol", None)
        if rvol_out is not None:
            meta = getattr(rvol_out, "metadata", None) or {}
            rvol_val = meta.get("rvol")
            if rvol_val is None:
                rvol_val = getattr(rvol_out, "value", None)
        candles = getattr(row, "candles", None) or []

        if not portfolios:
            result = sync_position(
                session,
                symbol=row.symbol,
                timeframe=row.timeframe,
                source="auto_watchlist",
                user_id=None,
                price=row.price,
                pipeline=row.pipeline,
                stop_distance=stop,
                signal_extra={"rvol": rvol_val, "atr_stop": stop},
            )
            marks[f"{row.symbol}:{row.timeframe}"] = row.price
            if result is not None:
                touched.append(result)
            continue

        for portfolio in portfolios:
            profile = portfolio.strategy_profile or {}
            det_key = (
                ",".join(profile.get("structure_detectors") or []),
                str(profile.get("structure_filter")),
                str(profile.get("structure_include_pytrendline")),
            )
            cache_key = (row.symbol, row.timeframe, "|".join(det_key))
            if profile.get("structure_filter") and cache_key in gate_cache:
                struct_gate = gate_cache[cache_key]
            else:
                struct_gate = apply_structure_gate(
                    row.pipeline,
                    candles,
                    profile,
                    rvol=rvol_val if isinstance(rvol_val, (int, float)) else None,
                )
                if profile.get("structure_filter"):
                    gate_cache[cache_key] = struct_gate

            # Fibonacci runs after structure (swings), then context
            fib_gate = apply_fibonacci_gate(struct_gate.pipeline, candles, profile)
            ctx_gate = apply_context_gate(fib_gate.pipeline, candles, profile)

            blocked = struct_gate.blocked or fib_gate.blocked or ctx_gate.blocked
            final_pipeline = ctx_gate.pipeline
            raw_decision = struct_gate.raw_decision
            if ctx_gate.blocked:
                block_reason, block_source = ctx_gate.reason, "context"
            elif fib_gate.blocked:
                block_reason, block_source = fib_gate.reason, "fibonacci"
            elif struct_gate.blocked:
                block_reason, block_source = struct_gate.reason, "structure"
            else:
                block_reason, block_source = None, None

            if blocked and profile.get("shadow_on_block"):
                shadow_broker.open_shadow(
                    session,
                    portfolio=portfolio,
                    symbol=row.symbol,
                    timeframe=row.timeframe,
                    raw_decision=raw_decision,
                    price=row.price,
                    stop_distance=stop if isinstance(stop, (int, float)) else None,
                    block_source=block_source or "unknown",
                    block_reason=block_reason,
                    meta={
                        "market_structure": struct_gate.structure_payload,
                        "fibonacci": fib_gate.fibonacci_payload,
                        "context": ctx_gate.context_payload,
                    },
                )

            extra: dict[str, Any] = {
                "rvol": rvol_val,
                "atr_stop": stop,
                "portfolio_code": portfolio.code,
            }
            if struct_gate.structure_payload is not None:
                extra["market_structure"] = struct_gate.structure_payload
            if fib_gate.fibonacci_payload is not None:
                extra["fibonacci"] = fib_gate.fibonacci_payload
            if ctx_gate.context_payload is not None:
                extra["context"] = ctx_gate.context_payload
            if blocked:
                extra["structure_blocked"] = struct_gate.blocked
                extra["fibonacci_blocked"] = fib_gate.blocked
                extra["context_blocked"] = ctx_gate.blocked
                extra["block_source"] = block_source
                extra["block_reason"] = block_reason
                extra["raw_decision"] = raw_decision

            result = sync_position(
                session,
                symbol=row.symbol,
                timeframe=row.timeframe,
                source="auto_watchlist",
                user_id=None,
                price=row.price,
                pipeline=final_pipeline,
                stop_distance=stop,
                signal_extra=extra,
                portfolio=portfolio,
            )
            if result is not None:
                touched.append(result)

        marks[f"{row.symbol}:{row.timeframe}"] = row.price

    shadow_broker.mark_shadows(session, marks=marks)

    for portfolio in portfolios:
        paper_broker.snapshot_equity(session, portfolio, marks=marks)
    session.commit()
    return touched


def open_user_confirmed(
    session: Session,
    *,
    symbol: str,
    timeframe: str,
    user_id: str,
    price: float,
    pipeline: PipelineResult,
    stop_distance: float | None = None,
) -> PaperPosition | None:
    existing = _get_open_position(
        session, symbol=symbol, timeframe=timeframe, source="user_confirmed", user_id=user_id
    )
    if existing is not None:
        return existing

    direction = _direction_for(pipeline.decision)
    if direction is None:
        return None

    position = sync_position(
        session,
        symbol=symbol,
        timeframe=timeframe,
        source="user_confirmed",
        user_id=user_id,
        price=price,
        pipeline=pipeline,
        stop_distance=stop_distance,
    )
    session.commit()
    return position


def close_manually(session: Session, position_id: str, *, price: float) -> PaperPosition | None:
    position = session.get(PaperPosition, position_id)
    if position is None or position.status != "OPEN":
        return None
    if position.qty:
        paper_broker.close_capital_position(
            session, position, price=price, reason="manual_close", signal=None
        )
    else:
        _close_legacy(position, price=price, reason="manual_close")
    session.commit()
    return position


def get_position(session: Session, position_id: str) -> PaperPosition | None:
    return session.get(PaperPosition, position_id)


def list_positions(
    session: Session,
    *,
    source: str | None = None,
    user_id: str | None = None,
    status: str | None = None,
    portfolio_id: str | None = None,
) -> list[PaperPosition]:
    stmt = select(PaperPosition).order_by(PaperPosition.entry_time.desc())
    if source is not None:
        stmt = stmt.where(PaperPosition.source == source)
    if user_id is not None:
        stmt = stmt.where(PaperPosition.user_id == user_id)
    if status is not None:
        stmt = stmt.where(PaperPosition.status == status)
    if portfolio_id is not None:
        stmt = stmt.where(PaperPosition.portfolio_id == portfolio_id)
    return list(session.execute(stmt).scalars().all())
