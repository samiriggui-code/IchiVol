"""Paper trading -- virtual positions only.

Phase 1 PaperBroker: ATR sizing against portfolio capital.
Phase 2: multi-portfolio sync + optional Market Structure gates on
experimental profiles only. ICHIVOL_BASELINE_V1 never gains structure filters.
Never a real order.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Sequence

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.db.models import PaperPortfolio, PaperPosition
from app.decision.pipeline import PipelineResult
from app.context.gate import apply_context_gate
from app.fibonacci.gate import apply_fibonacci_gate
from app.market_data.timeframes import TF_SECONDS
from app.paper import broker as paper_broker
from app.paper import counters as paper_counters
from app.paper import gates as paper_gates
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


def _lock_symbol(session: Session, portfolio_id: str | None, symbol: str) -> None:
    """Serialise concurrent opens for one (portfolio, symbol).

    ``SELECT ... FOR UPDATE`` only locks rows that already exist, so two
    simultaneous confirmations on a symbol with no open lot would both insert.
    A transaction-scoped advisory lock closes that race without a schema change;
    it is released at commit/rollback."""
    if portfolio_id is None:
        return
    bind = session.get_bind()
    if bind is not None and bind.dialect.name == "postgresql":
        session.execute(
            text("select pg_advisory_xact_lock(hashtext(:k))"), {"k": f"open:{portfolio_id}:{symbol}"}
        )


def _get_open_by_symbol(
    session: Session,
    *,
    symbol: str,
    portfolio_id: str,
    for_update: bool = False,
) -> PaperPosition | None:
    """Any open lot on this symbol in the portfolio (any TF / source).

    Prevents double-investing the same asset via a second click or a second
    timeframe while one lot is already open.
    """
    stmt = select(PaperPosition).where(
        PaperPosition.symbol == symbol,
        PaperPosition.portfolio_id == portfolio_id,
        PaperPosition.status == "OPEN",
    )
    if for_update:
        stmt = stmt.with_for_update()
    return session.execute(stmt).scalars().first()


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
    decision_id: str | None = None,
    evidence_id: str | None = None,
    run_id: int | None = None,
    manual_notional: float | None = None,
    take_profit_r: float | None = None,
) -> PaperPosition | None:
    """One symbol open/hold/close for one portfolio. Capital sizing when stop set."""
    if portfolio is None:
        try:
            portfolio = ensure_baseline_portfolio(session)
        except Exception:
            portfolio = None

    portfolio_id = portfolio.id if portfolio is not None else None
    _lock_symbol(session, portfolio_id, symbol)
    existing = _get_open_position(
        session,
        symbol=symbol,
        timeframe=timeframe,
        source=source,
        user_id=user_id,
        portfolio_id=portfolio_id,
    )
    # One open lot per symbol per portfolio — blocks a second TF/source invest.
    if existing is None and portfolio_id is not None:
        existing = _get_open_by_symbol(session, symbol=symbol, portfolio_id=portfolio_id)
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

        _prof = (portfolio.strategy_profile or {}) if portfolio is not None else {}
        if _prof.get("exit_mode") == "direction" and existing.source == source:
            # Long-only forward test (FWD_E_LONG): a lot closes on stop/target (above) or when the
            # Ichimoku DIRECTION of the last closed bar is no longer the lot's direction. A decision that
            # merely falls back to WATCH/NO_TRADE never closes it.
            if existing.timeframe != timeframe:
                return None  # a lot is only managed by the row of its own timeframe
            _pdir = getattr(pipeline.direction, "value", str(pipeline.direction))
            if _pdir == existing.direction:
                return None
            if existing.qty:
                paper_broker.close_capital_position(
                    session, existing, price=price, reason="direction_flipped", signal=signal
                )
            else:
                _close_legacy(existing, price=price, reason="direction_flipped")
            session.flush()
            return existing

        if direction == existing.direction:
            # A signal blocked by a lot opened from another source/timeframe is a real rejection; the same lot
            # seen again every cycle is not (it would inflate the counter), so only the former is journaled.
            pf_profile = (portfolio.strategy_profile or {}) if portfolio is not None else {}
            if pf_profile.get("log_rejections") and (existing.source != source or existing.timeframe != timeframe):
                paper_counters.record_rejection(
                    session, portfolio, symbol=symbol, timeframe=timeframe, reason="position_already_open",
                    detail={"held_source": existing.source, "held_timeframe": existing.timeframe},
                )
            return None

        if existing.source != source:
            # A lot opened from another source (e.g. user_confirmed) is NOT managed by this loop's
            # signal: a signal downgrade must never close a manual position. Only its stop/target
            # (checked above, and by app/paper/protection.py) or the user can close it.
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

    profile = (portfolio.strategy_profile or {}) if portfolio is not None else {}
    log_rej = bool(profile.get("log_rejections")) and portfolio is not None
    if direction == "SHORT" and portfolio is not None and profile.get("allow_short", True) is False:
        # No short selling on this portfolio, ever. Does not consume the signal run (no gate call).
        if log_rej:
            paper_counters.record_rejection(session, portfolio, symbol=symbol, timeframe=timeframe, reason="short_not_allowed")
        return None
    if portfolio is not None and manual_notional is None and paper_gates.has_gates(profile):
        # (a user-chosen amount is validated with its real numbers by app.paper.manual before it gets here)
        # Optional experimental gates (all OFF for the baseline): first failing reason wins.
        reason = paper_gates.entry_gate(
            session, portfolio, symbol=symbol, timeframe=timeframe, price=price,
            stop_distance=stop_distance, equity=paper_broker.estimate_equity(session, portfolio), run_id=run_id,
        )
        if reason is not None:
            if log_rej:
                paper_counters.record_rejection(session, portfolio, symbol=symbol, timeframe=timeframe, reason=reason)
            return None

    if portfolio is not None and stop_distance and stop_distance > 0:
        require_atr = bool(profile.get("require_atr_stop", True))
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
            decision_id=decision_id,
            evidence_id=evidence_id,
            manual_notional=manual_notional,
            take_profit_r=take_profit_r,
        )
        if position is not None:
            session.flush()
            if run_id is not None:
                paper_gates.mark_run_traded(portfolio.id, symbol, timeframe, run_id)
            return position
        if log_rej:
            opened = paper_gates.open_positions(session, portfolio.id)
            paper_counters.record_rejection(
                session, portfolio, symbol=symbol, timeframe=timeframe,
                reason="max_positions" if len(opened) >= int(profile.get("max_open_positions", 5))
                else "insufficient_cash_or_size",
            )
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
    funnel_portfolio = next((pf for pf in portfolios if (pf.strategy_profile or {}).get("log_rejections")), None)
    funnels: dict[str, paper_counters.FunnelAccumulator] = {}
    bars_by_key: dict[str, Sequence] = {}
    now_s = datetime.now(timezone.utc).timestamp()

    for row in rows:
        bars_by_key[f"{row.symbol}:{row.timeframe}"] = getattr(row, "candles", None) or []
        if funnel_portfolio is not None and getattr(row, "candles", None):
            tf_s = TF_SECONDS.get(row.timeframe, 3600)
            last_open = row.candles[-1].time
            funnels.setdefault(row.timeframe, paper_counters.FunnelAccumulator()).add(
                paper_counters.classify_row(
                    row.pipeline,
                    bar_forming=last_open + tf_s > now_s,
                    stale=now_s - (last_open + tf_s) > 2 * tf_s,
                )
            )
        if (getattr(row, "signal_timing", None) or {}).get("stale"):
            # Frozen/late provider data (e.g. TONUSDT candles stopped 2026-06-30): do not open,
            # do not close on the signal, do not mark open lots to a stale price. Protections
            # are watched separately by app/paper/protection.py.
            continue
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

            run_id = None
            if paper_gates.has_gates(profile):
                run_id = paper_gates.observe_decision(
                    portfolio.id, row.symbol, row.timeframe, final_pipeline.decision
                )
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
                run_id=run_id,
            )
            if result is not None:
                touched.append(result)

        marks[f"{row.symbol}:{row.timeframe}"] = row.price

    if funnel_portfolio is not None:
        for tf, acc in funnels.items():
            paper_counters.record_funnel(session, funnel_portfolio, acc, tf)

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
    decision_id: str | None = None,
    evidence_id: str | None = None,
    signal_extra: dict[str, Any] | None = None,
    manual_notional: float | None = None,
    take_profit_r: float | None = None,
) -> tuple[PaperPosition | None, bool]:
    """Open a user-confirmed paper lot.

    Returns ``(position, created)``. ``created=False`` means an open lot on
    this symbol already existed in the baseline portfolio — idempotent lock,
    no second notional spent.
    """
    portfolio = ensure_baseline_portfolio(session)
    _lock_symbol(session, portfolio.id, symbol)
    existing_any = _get_open_by_symbol(
        session, symbol=symbol, portfolio_id=portfolio.id, for_update=True
    )
    if existing_any is not None:
        return existing_any, False

    existing = _get_open_position(
        session, symbol=symbol, timeframe=timeframe, source="user_confirmed", user_id=user_id
    )
    if existing is not None:
        return existing, False

    direction = _direction_for(pipeline.decision)
    if direction is None:
        return None, False

    position = sync_position(
        session,
        symbol=symbol,
        timeframe=timeframe,
        source="user_confirmed",
        user_id=user_id,
        price=price,
        pipeline=pipeline,
        stop_distance=stop_distance,
        decision_id=decision_id,
        evidence_id=evidence_id,
        signal_extra=signal_extra,
        portfolio=portfolio,
        manual_notional=manual_notional,
        take_profit_r=take_profit_r,
    )
    session.commit()
    return position, position is not None


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
