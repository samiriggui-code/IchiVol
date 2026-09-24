"""Virtual paper broker — fills, cash, stops/TP, journal. Never real orders."""

from __future__ import annotations

import math
from datetime import datetime, timezone
from dataclasses import replace as _replace
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import (
    PaperEquitySnapshot,
    PaperJournalEvent,
    PaperPartialExit,
    PaperPortfolio,
    PaperPosition,
    PaperReinforceAdd,
)
from app.brokerage import persistence as ledger_db
from app.brokerage.execution import fill_at_quote
from app.brokerage.fee_profiles import get_schedule
from app.brokerage.ledger import Cause, Leg
from app.market_data.contracts import ExecutionMode, Quote
from app.paper import orders as paper_orders
from app.paper.risk import apply_exit_friction, size_position
from app.paper.strategy_profiles import BASELINE_PROFILE


def _profile(portfolio: PaperPortfolio) -> dict[str, Any]:
    return portfolio.strategy_profile or dict(BASELINE_PROFILE)


def _fee_meta(profile: dict[str, Any]) -> dict[str, Any]:
    fid = profile.get("fee_profile_id")
    if not fid:
        return {"model": "legacy_bps", "commission_bps": float(profile.get("commission_bps", 5.0))}
    sch = get_schedule(fid)
    return {"model": "schedule", "id": sch.id, "version": sch.version, "source": sch.source}


def _commission_bps(profile: dict[str, Any], symbol: str | None) -> float:
    by_symbol = profile.get("commission_bps_by_symbol") or {}
    if symbol is not None and symbol in by_symbol:
        return float(by_symbol[symbol])
    return float(profile.get("commission_bps", 5.0))


def _commission(profile: dict[str, Any], notional: float, qty: float, symbol: str | None = None) -> float:
    """Whole-order commission: versioned schedule when the profile names one,
    else the legacy flat-bps rule (unchanged for existing portfolios)."""
    fid = profile.get("fee_profile_id")
    if not fid:
        return notional * (_commission_bps(profile, symbol) / 10_000.0)
    return float(get_schedule(fid).order_fee(ledger_db.to_decimal(notional), ledger_db.to_decimal(qty)))


def _friction(profile: dict[str, Any], symbol: str) -> tuple[float, float]:
    """(spread_bps, slippage_bps) per side. ``friction_bps_by_symbol`` (documented assumption table)
    gives the combined per-side friction and replaces both defaults for that symbol."""
    table = profile.get("friction_bps_by_symbol") or {}
    if symbol in table:
        return float(table[symbol]), 0.0
    return float(profile.get("spread_bps", 2.0)), float(profile.get("slippage_bps", 3.0))


def _lock_portfolio(session: Session, portfolio: PaperPortfolio | None) -> None:
    """Serialise cash read-modify-write per portfolio (row lock held until commit)."""
    if portfolio is None:
        return
    bind = session.get_bind()
    if bind is not None and bind.dialect.name == "postgresql":
        session.flush()  # keep pending changes of this transaction before reloading
        session.execute(select(PaperPortfolio.id).where(PaperPortfolio.id == portfolio.id).with_for_update()).all()
        session.refresh(portfolio)


def _count_open(session: Session, portfolio_id: str) -> int:
    return int(
        session.execute(
            select(func.count())
            .select_from(PaperPosition)
            .where(
                PaperPosition.portfolio_id == portfolio_id,
                PaperPosition.status.in_(("OPEN", "CLOSING")),
            )
        ).scalar_one()
    )


def _journal(
    session: Session,
    *,
    portfolio_id: str,
    position_id: str | None,
    event_type: str,
    payload: dict[str, Any],
) -> None:
    session.add(
        PaperJournalEvent(
            portfolio_id=portfolio_id,
            position_id=position_id,
            event_type=event_type,
            payload=payload,
            created_at=datetime.now(timezone.utc),
        )
    )



def _ensure_initial_entry_refs(position: PaperPosition, *, remaining: float, prior_sold: float) -> None:
    """Freeze initial_qty / initial_entry_fee before any shrink (OPEN path)."""
    if position.initial_qty is None:
        position.initial_qty = remaining + prior_sold
    if position.initial_entry_fee is None:
        iq = float(position.initial_qty or 0.0)
        fee_now = float(position.entry_fee or 0.0)
        if iq > 0 and remaining + 1e-12 < iq and remaining > 1e-12:
            # Already scaled out without the column — reconstruct full entry fee.
            position.initial_entry_fee = fee_now * (iq / remaining)
        else:
            position.initial_entry_fee = fee_now


def _total_entered_qty_fee(
    session: Session, position: PaperPosition
) -> tuple[float, float]:
    """Original open + Σ reinforce adds (stable CLOSE display size)."""
    iq = float(position.initial_qty) if position.initial_qty is not None else float(position.qty or 0.0)
    ifee = (
        float(position.initial_entry_fee)
        if position.initial_entry_fee is not None
        else float(position.entry_fee or 0.0)
    )
    adds = list(
        session.execute(
            select(PaperReinforceAdd).where(PaperReinforceAdd.position_id == position.id)
        ).scalars()
    )
    return iq + sum(float(a.qty or 0.0) for a in adds), ifee + sum(
        float(a.fee or 0.0) for a in adds
    )


def _restore_entry_refs_after_close(session: Session, position: PaperPosition) -> None:
    """Restore qty / entry_fee / notional to total entered (open + renforts).

    ``initial_qty`` / ``initial_entry_fee`` stay the original open refs;
    displayed CLOSED size is initial + Σ ``paper_reinforce_adds``.
    """
    if position.initial_qty is None:
        position.initial_qty = float(position.qty or 0.0)
    if position.initial_entry_fee is None:
        position.initial_entry_fee = float(position.entry_fee or 0.0)

    total_qty, total_fee = _total_entered_qty_fee(session, position)
    position.qty = total_qty
    position.entry_fee = total_fee
    avg = float(position.entry_price or 0.0)
    position.notional = avg * total_qty if total_qty else 0.0


def _apply_vwap_pnl_pct(
    session: Session,
    position: PaperPosition,
    *,
    extra_fill: tuple[float, float] | None = None,
) -> None:
    """Set ``pnl_pct`` from qty-weighted VWAP of partial exits + optional final fill."""
    from app.strategy_lab.partial_tp import vwap_exit

    exits = list(
        session.execute(
            select(PaperPartialExit).where(PaperPartialExit.position_id == position.id)
        ).scalars()
    )
    fills: list[tuple[float, float]] = [
        (float(e.price), float(e.qty or 0.0)) for e in exits if float(e.qty or 0.0) > 0
    ]
    if extra_fill is not None and extra_fill[1] > 0:
        fills.append(extra_fill)
    if not fills:
        px = float(position.exit_price or position.entry_price or 0.0)
        q = float(position.initial_qty or position.qty or 0.0)
        if q <= 0 or px <= 0:
            return
        fills = [(px, q)]
    vwap = vwap_exit(fills)
    if position.direction == "LONG":
        position.pnl_pct = (vwap / position.entry_price) - 1.0
    else:
        position.pnl_pct = short_pnl_pct(position.entry_price, vwap)


def short_pnl_pct(entry_price: float, exit_fill: float) -> float:
    """SHORT return: (entry − exit) / entry. Never use entry/exit − 1 (overstates gains)."""
    if not entry_price:
        return 0.0
    return (entry_price - exit_fill) / entry_price


def short_realized_currency(qty: float, entry_price: float, exit_fill: float) -> float:
    """SHORT P&L in quote currency before fees: qty × (entry − exit)."""
    return float(qty) * (float(entry_price) - float(exit_fill))


def open_capital_position(
    session: Session,
    *,
    portfolio: PaperPortfolio,
    symbol: str,
    timeframe: str,
    source: str,
    user_id: str | None,
    direction: str,
    price: float,
    decision: str,
    stop_distance: float,
    signal: dict[str, Any] | None = None,
    decision_id: str | None = None,
    evidence_id: str | None = None,
    quote: Quote | None = None,
    manual_notional: float | None = None,
    take_profit_r: float | None = None,
) -> PaperPosition | None:
    """Open a sized paper position. Returns None if risk/cash/caps block it.
    ``manual_notional`` / ``take_profit_r``: discretionary order chosen by the user (see risk._size_manual)."""
    _lock_portfolio(session, portfolio)
    profile = _profile(portfolio)
    max_open = int(profile.get("max_open_positions", 5))
    if _count_open(session, portfolio.id) >= max_open:
        return None

    equity = estimate_equity(session, portfolio)
    side = "BUY" if direction == "LONG" else "SELL"
    quoted = quote is not None
    if quoted:
        # Real bid/ask: the spread is already in the fill price, so no extra spread/slippage.
        ref_price = quote.ask if side == "BUY" else quote.bid
        spread_bps, slippage_bps = 0.0, 0.0
    else:
        ref_price = price
        spread_bps, slippage_bps = _friction(profile, symbol)
    sized = size_position(
        equity=equity,
        cash=portfolio.cash,
        direction=direction,
        entry_price=ref_price,
        stop_distance=stop_distance,
        risk_pct=float(profile.get("risk_pct", 0.01)),
        take_profit_r=float(take_profit_r if take_profit_r is not None else profile.get("take_profit_r", 2.0)),
        max_notional_pct=float(profile.get("max_notional_pct", 0.25)),
        commission_bps=_commission_bps(profile, symbol),
        spread_bps=spread_bps,
        slippage_bps=slippage_bps,
        min_fill_fraction=float(profile.get("min_fill_fraction", 0.25)),
        min_notional=float(profile.get("min_notional", 10.0)),
        manual_notional=manual_notional,
    )
    if sized is None:
        return None
    exec_meta: dict[str, Any] = {
        "model": ExecutionMode.CANDLE_ONLY.value,
        "spread_bps": spread_bps,
        "slippage_bps": slippage_bps,
    }
    if quoted:
        fill = fill_at_quote(side, sized.qty, quote)
        if fill.rejected:
            return None
        if fill.is_partial:
            qty = fill.filled_qty
            sized = _replace(sized, qty=qty, notional=qty * sized.entry_fill, risk_amount=qty * stop_distance)
        exec_meta = {
            "model": fill.model.value,
            "reason": fill.reason,
            "assumptions": list(fill.assumptions),
            "quote_source": quote.provenance.source,
            "quote_received_at": quote.provenance.received_at.isoformat(),
            "bid": quote.bid,
            "ask": quote.ask,
        }

    fee = _commission(profile, sized.notional, sized.qty, symbol)
    if not all(math.isfinite(x) for x in (sized.notional, sized.qty, fee, sized.entry_fill)):
        return None
    if sized.notional + fee > portfolio.cash:
        return None

    now = datetime.now(timezone.utc)
    bar_key = paper_orders.resolve_open_bar_key(
        signal, decision_id=decision_id, intent_ref=(signal or {}).get("intent_ref")
    )
    if not bar_key:
        _journal(
            session,
            portfolio_id=portfolio.id,
            position_id=None,
            event_type="ORDER_REFUSED",
            payload={"code": "no_bar_key", "symbol": symbol, "timeframe": timeframe},
        )
        return None
    coid = paper_orders.client_order_id_open(
        portfolio_id=portfolio.id,
        symbol=symbol,
        timeframe=timeframe,
        side=side,
        bar_key=bar_key,
    )
    prior = paper_orders.get_by_client_order_id(session, portfolio.id, coid)
    if prior is not None and prior.status == paper_orders.FILLED and prior.position_id:
        # Idempotent resubmit: zero 2nd fill / ledger / cash debit
        return session.get(PaperPosition, prior.position_id)
    if prior is not None and prior.status in paper_orders.TERMINAL and prior.status != paper_orders.FILLED:
        # create_order would return this terminal non-FILLED — no open effect
        return None

    position = PaperPosition(
        portfolio_id=portfolio.id,
        symbol=symbol,
        timeframe=timeframe,
        source=source,
        user_id=user_id,
        direction=direction,
        status="OPEN",
        entry_time=now,
        entry_price=sized.entry_fill,
        entry_decision=decision,
        entry_signal=signal or {},
        qty=sized.qty,
        initial_qty=sized.qty,
        notional=sized.notional,
        stop_price=sized.stop_price,
        take_profit_price=sized.take_profit_price,
        risk_pct=sized.risk_pct,
        risk_amount=sized.risk_amount,
        entry_fee=fee,
        initial_entry_fee=fee,
        mfe_pct=0.0,
        mae_pct=0.0,
        highest_price_seen=sized.entry_fill,
        lowest_price_seen=sized.entry_fill,
        decision_id=decision_id,
        evidence_id=evidence_id,
        created_at=now,
        updated_at=now,
    )
    session.add(position)
    session.flush()

    order = paper_orders.create_order(
        session,
        portfolio_id=portfolio.id,
        client_order_id=coid,
        position_id=position.id,
        symbol=symbol,
        timeframe=timeframe,
        side=side,
        order_type="MARKET",
        requested_price=price,
        qty=sized.qty,
        notional=sized.notional,
        fee=fee,
        spread_bps=spread_bps,
        slippage_bps=slippage_bps,
        reason="open",
        intent_ref=(signal or {}).get("intent_ref") if signal else None,
        at=now,
    )
    if order.status in paper_orders.TERMINAL and order.status != paper_orders.FILLED:
        session.delete(position)
        session.flush()
        return None
    if order.status == paper_orders.FILLED:
        # Race: create_order returned existing FILLED — drop orphan position if different
        if order.position_id and order.position_id != position.id:
            session.delete(position)
            session.flush()
            return session.get(PaperPosition, order.position_id)
        return position

    paper_orders.submit_ack_fill_market(
        session,
        order,
        filled_price=sized.entry_fill,
        filled_qty=sized.qty,
        fee=fee,
        notional=sized.notional,
        reason="open",
        at=now,
    )
    if order.status != paper_orders.FILLED:
        session.delete(position)
        session.flush()
        return None

    ledger_db.guarded(session, portfolio.id, position.id, "opening", lambda: ledger_db.ensure_opening(session, portfolio, now))
    portfolio.cash -= sized.notional + fee
    portfolio.updated_at = now
    ledger_db.guarded(
        session, portfolio.id, position.id, "open",
        lambda: ledger_db.post(
            session,
            portfolio.id,
            f"open:{position.id}",
            now,
            [
                Leg(portfolio.currency, -ledger_db.to_decimal(sized.notional), Cause.EXECUTION, f"{side} {symbol}"),
                Leg(portfolio.currency, -ledger_db.to_decimal(fee), Cause.COMMISSION, "entry commission"),
            ],
            ref=position.id,
        ),
    )
    _journal(
        session,
        portfolio_id=portfolio.id,
        position_id=position.id,
        event_type="OPENED",
        payload={
            "symbol": symbol,
            "direction": direction,
            "entry": sized.entry_fill,
            "stop": sized.stop_price,
            "take_profit": sized.take_profit_price,
            "qty": sized.qty,
            "risk_pct": sized.risk_pct,
            "decision": decision,
            "protection_monitored": True,
            "fee": _fee_meta(profile) | {"amount": fee},
            "execution": exec_meta,
            "client_order_id": coid,
            "bar_key": bar_key,
        },
    )
    return position


def close_capital_position(
    session: Session,
    position: PaperPosition,
    *,
    price: float,
    reason: str,
    signal: dict[str, Any] | None = None,
    quote: Quote | None = None,
    at: datetime | None = None,
) -> PaperPosition:
    if position.status == "CLOSED":
        return position  # replay/double close: no second credit, no second order
    if position.status not in ("OPEN", "CLOSING"):
        return position
    if not math.isfinite(float(price)):
        raise ValueError(f"non-finite exit price: {price!r}")
    portfolio = session.get(PaperPortfolio, position.portfolio_id) if position.portfolio_id else None
    _lock_portfolio(session, portfolio)
    bind = session.get_bind()
    if portfolio is not None and bind is not None and bind.dialect.name == "postgresql":
        # Another transaction (auto loop / monitor) may have closed this lot while we waited for the
        # portfolio lock: reload it and re-check, otherwise cash would be credited twice.
        session.refresh(position)
        if position.status == "CLOSED":
            return position
        if position.status not in ("OPEN", "CLOSING"):
            return position
    profile = _profile(portfolio) if portfolio is not None else dict(BASELINE_PROFILE)
    now = at or datetime.now(timezone.utc)

    # Fermeture demandée ≠ position fermée
    if position.status == "OPEN":
        position.status = "CLOSING"
        position.close_requested_at = now
        position.updated_at = now
        session.flush()

    def _revert_open(*, order_reason: str, codes: list[str] | None = None) -> PaperPosition:
        position.status = "OPEN"
        position.close_requested_at = None
        position.updated_at = now
        if portfolio is not None:
            _journal(
                session,
                portfolio_id=portfolio.id,
                position_id=position.id,
                event_type="CLOSE_REJECTED",
                payload={"reason": order_reason, "codes": codes or []},
            )
        return position

    exit_fill = price
    exit_fee = 0.0
    realized = None
    close_exec = None
    exit_spread_bps = exit_slip_bps = 0.0

    if position.qty and position.qty > 0 and portfolio is not None:
        coid, existing = paper_orders.resolve_close_client_order_id(
            session, portfolio.id, position.id
        )
        if existing is not None and existing.status == paper_orders.FILLED:
            if position.status != "CLOSED":
                position.status = "CLOSED"
                position.exit_time = position.exit_time or existing.created_at
                position.exit_price = existing.filled_price
                position.exit_reason = reason
                position.close_requested_at = None
                position.updated_at = now
            return position
        if existing is not None and existing.status in paper_orders.TERMINAL:
            # Should not happen (resolver skips terminal non-FILLED) — belt & braces
            return _revert_open(order_reason="terminal_non_filled", codes=["order_terminal"])

        side = "SELL" if position.direction == "LONG" else "BUY"
        order = paper_orders.create_order(
            session,
            portfolio_id=portfolio.id,
            client_order_id=coid,
            position_id=position.id,
            symbol=position.symbol,
            timeframe=position.timeframe,
            side=side,
            order_type="MARKET",
            requested_price=price,
            qty=float(position.qty),
            notional=float(position.qty) * float(price),
            fee=0.0,
            reason=reason,
            at=now,
        )
        if order.status in paper_orders.TERMINAL and order.status != paper_orders.FILLED:
            return _revert_open(order_reason=order.reason or "terminal_non_filled", codes=["order_terminal"])
        if order.status == paper_orders.FILLED:
            if position.status != "CLOSED":
                position.status = "CLOSED"
                position.exit_time = position.exit_time or now
                position.exit_price = order.filled_price
                position.exit_reason = reason
                position.close_requested_at = None
                position.updated_at = now
            return position

        try:
            if quote is not None:
                exit_fill = quote.bid if position.direction == "LONG" else quote.ask
                exit_spread_bps = exit_slip_bps = 0.0
                close_exec = {
                    "model": ExecutionMode.QUOTE_BASED.value,
                    "bid": quote.bid,
                    "ask": quote.ask,
                    "quote_source": quote.provenance.source,
                }
            else:
                exit_spread_bps, exit_slip_bps = _friction(profile, position.symbol)
                exit_fill = apply_exit_friction(
                    price,
                    direction=position.direction,
                    spread_bps=exit_spread_bps,
                    slippage_bps=exit_slip_bps,
                )
                close_exec = {
                    "model": ExecutionMode.CANDLE_ONLY.value,
                    "spread_bps": exit_spread_bps,
                    "slippage_bps": exit_slip_bps,
                }
            if not math.isfinite(float(exit_fill)):
                raise ValueError(f"non-finite exit fill: {exit_fill!r}")
            exit_fee = _commission(profile, position.qty * exit_fill, position.qty, position.symbol)
            if not math.isfinite(float(exit_fee)):
                raise ValueError(f"non-finite exit fee: {exit_fee!r}")
        except Exception as exc:
            paper_orders.reject_order(
                session,
                order,
                reason="fill_failed",
                codes=["fill_failed", type(exc).__name__],
                at=now,
            )
            return _revert_open(order_reason="fill_failed", codes=["fill_failed", type(exc).__name__])

        # Fill first — zero cash / ledger / CLOSED until FILLED
        order.spread_bps = exit_spread_bps
        order.slippage_bps = exit_slip_bps
        paper_orders.submit_ack_fill_market(
            session,
            order,
            filled_price=exit_fill,
            filled_qty=float(position.qty),
            fee=exit_fee,
            notional=float(position.qty) * exit_fill,
            reason=reason,
            at=now,
        )
        if order.status != paper_orders.FILLED:
            paper_orders.reject_order(
                session, order, reason="fill_incomplete", codes=["fill_incomplete"], at=now
            )
            return _revert_open(order_reason="fill_incomplete", codes=["fill_incomplete"])

        ledger_db.guarded(session, portfolio.id, position.id, "opening", lambda: ledger_db.ensure_opening(session, portfolio, now))
        cash_before = portfolio.cash
        entry_notional = position.notional or 0.0
        from app.paper.financing import financing_total_for_position

        financing_paid = financing_total_for_position(session, position.id)
        prior_realized = float(position.realized_pnl or 0.0)
        if position.direction == "LONG":
            proceeds = position.qty * exit_fill
            slice_realized = (
                proceeds - exit_fee - entry_notional - (position.entry_fee or 0.0) - financing_paid
            )
            portfolio.cash += proceeds - exit_fee
        else:
            pnl_currency = short_realized_currency(position.qty, position.entry_price, exit_fill)
            slice_realized = (
                pnl_currency - exit_fee - (position.entry_fee or 0.0) - financing_paid
            )
            portfolio.cash += entry_notional + pnl_currency - exit_fee
        realized = prior_realized + slice_realized
        portfolio.realized_pnl += slice_realized
        portfolio.updated_at = now
        cash_delta = portfolio.cash - cash_before

        ledger_db.guarded(
            session, portfolio.id, position.id, "close",
            lambda: ledger_db.post(
                session,
                portfolio.id,
                f"close:{position.id}",
                now,
                [
                    Leg(
                        portfolio.currency,
                        ledger_db.to_decimal(cash_delta + exit_fee),
                        Cause.EXECUTION,
                        f"close {position.symbol} ({reason})",
                    ),
                    Leg(portfolio.currency, -ledger_db.to_decimal(exit_fee), Cause.COMMISSION, "exit commission"),
                ],
                ref=position.id,
            ),
        )
    elif position.qty and position.qty > 0 and portfolio is None:
        # No portfolio book — cannot place order; revert CLOSING
        return _revert_open(order_reason="no_portfolio", codes=["no_portfolio"])

    position.status = "CLOSED"
    position.exit_time = now
    position.exit_price = exit_fill
    position.exit_reason = reason
    position.exit_signal = signal
    position.close_requested_at = None
    position.exit_fee = (position.exit_fee or 0.0) + exit_fee
    position.realized_pnl = realized if realized is not None else position.realized_pnl
    closed_qty = float(position.qty or 0.0)
    _apply_vwap_pnl_pct(
        session,
        position,
        extra_fill=(exit_fill, closed_qty) if closed_qty > 0 else None,
    )
    _restore_entry_refs_after_close(session, position)
    position.updated_at = now

    if portfolio is not None:
        _journal(
            session,
            portfolio_id=portfolio.id,
            position_id=position.id,
            event_type="CLOSED",
            payload={
                "reason": reason,
                "exit": exit_fill,
                "pnl_pct": position.pnl_pct,
                "realized_pnl": position.realized_pnl,
                "fee": _fee_meta(profile) | {"amount": exit_fee},
                "execution": close_exec,
            },
        )
    return position


def partial_close_capital_position(
    session: Session,
    position: PaperPosition,
    *,
    price: float,
    qty: float,
    fraction: float,
    r_multiple: float,
    reason: str = "partial_tp",
    signal: dict[str, Any] | None = None,
    at: datetime | None = None,
    time_ms: int | None = None,
) -> PaperPartialExit | None:
    """Scale out ``qty`` (must be > 0 and ≤ remaining). Position stays OPEN if qty remains.

    Returns the journal row, or None if the lot was already closed / qty invalid.
    Never drives ``position.qty`` negative.

    When ``qty`` exhausts the lot (new_qty ≈ 0), settlement goes through
    ``close_capital_position`` so financing and entry_fee restore match a full close.
    """
    if position.status != "OPEN":
        return None
    if not math.isfinite(float(price)) or not math.isfinite(float(qty)):
        raise ValueError(f"non-finite partial price/qty: {price!r} {qty!r}")
    remaining = float(position.qty or 0.0)
    if qty <= 0 or remaining <= 0:
        return None
    if qty > remaining + 1e-12:
        raise ValueError(
            f"partial qty {qty} exceeds remaining {remaining} on {position.id}"
        )
    qty = min(qty, remaining)

    portfolio = session.get(PaperPortfolio, position.portfolio_id) if position.portfolio_id else None
    if portfolio is None:
        return None
    _lock_portfolio(session, portfolio)
    bind = session.get_bind()
    if bind is not None and bind.dialect.name == "postgresql":
        session.refresh(position)
        if position.status != "OPEN":
            return None
        remaining = float(position.qty or 0.0)
        if qty > remaining + 1e-12:
            return None
        qty = min(qty, remaining)

    profile = _profile(portfolio)
    now = at or datetime.now(timezone.utc)
    ts_ms = time_ms if time_ms is not None else int(now.timestamp() * 1000)

    existing = list(
        session.execute(
            select(PaperPartialExit)
            .where(PaperPartialExit.position_id == position.id)
            .order_by(PaperPartialExit.seq)
        ).scalars()
    )
    seq = (existing[-1].seq + 1) if existing else 1
    key = f"partial:{position.id}:{seq}"

    prior_sold = sum(float(e.qty or 0.0) for e in existing)
    _ensure_initial_entry_refs(position, remaining=remaining, prior_sold=prior_sold)

    # Idempotent replay
    prior = session.execute(
        select(PaperPartialExit).where(
            PaperPartialExit.portfolio_id == portfolio.id,
            PaperPartialExit.key == key,
        )
    ).scalar_one_or_none()
    if prior is not None:
        return prior

    # Exhausting scale-out: settle via close_capital_position (financing + entry_fee restore).
    if qty >= remaining - 1e-12:
        prior_realized = float(position.realized_pnl or 0.0)
        exit_fee_before = float(position.exit_fee or 0.0)
        close_capital_position(
            session,
            position,
            price=price,
            reason=reason,
            signal=signal,
            at=now,
        )
        slice_realized = float(position.realized_pnl or 0.0) - prior_realized
        exit_fee = float(position.exit_fee or 0.0) - exit_fee_before
        exit_fill = float(position.exit_price or price)
        row = PaperPartialExit(
            portfolio_id=portfolio.id,
            position_id=position.id,
            seq=seq,
            key=key,
            r_multiple=float(r_multiple),
            fraction=float(fraction),
            qty=qty,
            price=exit_fill,
            fee=exit_fee,
            realized_pnl=slice_realized,
            time_ms=ts_ms,
            created_at=now,
        )
        session.add(row)
        _journal(
            session,
            portfolio_id=portfolio.id,
            position_id=position.id,
            event_type="PARTIAL_TP",
            payload={
                "seq": seq,
                "r_multiple": r_multiple,
                "fraction": fraction,
                "qty": qty,
                "price": exit_fill,
                "realized_pnl": slice_realized,
                "remaining_qty": 0.0,
                "via": "close_capital_position",
                "signal": signal,
            },
        )
        session.flush()
        return row

    spread_bps, slip_bps = _friction(profile, position.symbol)
    exit_fill = apply_exit_friction(
        price,
        direction=position.direction,
        spread_bps=spread_bps,
        slippage_bps=slip_bps,
    )
    exit_fee = _commission(profile, qty * exit_fill, qty, position.symbol)

    share = qty / remaining
    entry_notional_share = float(position.notional or 0.0) * share
    entry_fee_share = float(position.entry_fee or 0.0) * share

    if position.direction == "LONG":
        proceeds = qty * exit_fill
        slice_realized = proceeds - exit_fee - entry_notional_share - entry_fee_share
    else:
        pnl_currency = short_realized_currency(qty, position.entry_price, exit_fill)
        slice_realized = pnl_currency - exit_fee - entry_fee_share

    coid = paper_orders.client_order_id_partial(position.id, seq)
    order = paper_orders.create_order(
        session,
        portfolio_id=portfolio.id,
        client_order_id=coid,
        position_id=position.id,
        symbol=position.symbol,
        timeframe=position.timeframe,
        side="SELL" if position.direction == "LONG" else "BUY",
        order_type="LIMIT",
        requested_price=price,
        qty=qty,
        notional=qty * exit_fill,
        fee=exit_fee,
        spread_bps=spread_bps,
        slippage_bps=slip_bps,
        reason=reason,
        at=now,
    )
    if order.status in paper_orders.TERMINAL and order.status != paper_orders.FILLED:
        return None
    if order.status != paper_orders.FILLED:
        paper_orders.submit_ack_fill_market(
            session,
            order,
            filled_price=exit_fill,
            filled_qty=qty,
            fee=exit_fee,
            notional=qty * exit_fill,
            reason=reason,
            at=now,
        )
    if order.status != paper_orders.FILLED:
        return None

    cash_before = portfolio.cash
    if position.direction == "LONG":
        portfolio.cash += proceeds - exit_fee
    else:
        portfolio.cash += entry_notional_share + pnl_currency - exit_fee

    portfolio.realized_pnl += slice_realized
    portfolio.updated_at = now
    cash_delta = portfolio.cash - cash_before

    ledger_db.guarded(
        session,
        portfolio.id,
        position.id,
        "partial",
        lambda: ledger_db.post(
            session,
            portfolio.id,
            key,
            now,
            [
                Leg(
                    portfolio.currency,
                    ledger_db.to_decimal(cash_delta + exit_fee),
                    Cause.EXECUTION,
                    f"partial {position.symbol} @ {r_multiple}R",
                ),
                Leg(
                    portfolio.currency,
                    -ledger_db.to_decimal(exit_fee),
                    Cause.COMMISSION,
                    "partial exit commission",
                ),
            ],
            ref=position.id,
        ),
    )

    row = PaperPartialExit(
        portfolio_id=portfolio.id,
        position_id=position.id,
        seq=seq,
        key=key,
        r_multiple=float(r_multiple),
        fraction=float(fraction),
        qty=qty,
        price=exit_fill,
        fee=exit_fee,
        realized_pnl=slice_realized,
        time_ms=ts_ms,
        created_at=now,
    )
    session.add(row)

    new_qty = remaining - qty
    if new_qty < 0:
        new_qty = 0.0
    position.qty = new_qty
    position.notional = float(position.notional or 0.0) * (1.0 - share)
    position.entry_fee = float(position.entry_fee or 0.0) * (1.0 - share)
    position.realized_pnl = float(position.realized_pnl or 0.0) + slice_realized
    position.exit_fee = float(position.exit_fee or 0.0) + exit_fee
    position.updated_at = now

    _journal(
        session,
        portfolio_id=portfolio.id,
        position_id=position.id,
        event_type="PARTIAL_TP",
        payload={
            "seq": seq,
            "r_multiple": r_multiple,
            "fraction": fraction,
            "qty": qty,
            "price": exit_fill,
            "realized_pnl": slice_realized,
            "remaining_qty": new_qty,
            "signal": signal,
        },
    )

    return row


def reinforce_add_capital_position(
    session: Session,
    position: PaperPosition,
    *,
    price: float,
    add_fraction: float,
    r_multiple: float,
    initial_qty: float,
    initial_risk: float,
    max_exposure: float = 1.0,
    risk_policy: str = "tighten_stop",
    reason: str = "reinforce",
    signal: dict[str, Any] | None = None,
    at: datetime | None = None,
    time_ms: int | None = None,
) -> PaperReinforceAdd | None:
    """Scale in under Lab risk invariant + notional/equity max_exposure + cash.

    Paper ``max_exposure`` caps ``notional_après_add ≤ max_exposure × equity``
    (not Lab's qty-unit cap). Refuses (returns None) on risk/exposure/cash
    violation — never partial-fills silently. Does not mutate ``initial_qty`` /
    ``initial_entry_fee``.
    """
    from app.agents.types import Direction
    from app.paper.risk import apply_entry_friction
    from app.strategy_lab.reinforce import (
        apply_reinforce_add,
        cap_add_by_notional_equity,
        open_risk,
    )

    if position.status != "OPEN":
        return None
    if not math.isfinite(float(price)) or not math.isfinite(float(add_fraction)):
        raise ValueError(f"non-finite reinforce price/fraction: {price!r} {add_fraction!r}")
    open_qty = float(position.qty or 0.0)
    if open_qty <= 0 or initial_qty <= 0:
        return None

    portfolio = session.get(PaperPortfolio, position.portfolio_id) if position.portfolio_id else None
    if portfolio is None:
        return None
    _lock_portfolio(session, portfolio)
    bind = session.get_bind()
    if bind is not None and bind.dialect.name == "postgresql":
        session.refresh(position)
        if position.status != "OPEN":
            return None
        open_qty = float(position.qty or 0.0)
        if open_qty <= 0:
            return None

    profile = _profile(portfolio)
    now = at or datetime.now(timezone.utc)
    ts_ms = time_ms if time_ms is not None else int(now.timestamp() * 1000)

    existing = list(
        session.execute(
            select(PaperReinforceAdd)
            .where(PaperReinforceAdd.position_id == position.id)
            .order_by(PaperReinforceAdd.seq)
        ).scalars()
    )
    seq = (existing[-1].seq + 1) if existing else 1
    key = f"reinforce:{position.id}:{seq}"
    prior = session.execute(
        select(PaperReinforceAdd).where(
            PaperReinforceAdd.portfolio_id == portfolio.id,
            PaperReinforceAdd.key == key,
        )
    ).scalar_one_or_none()
    if prior is not None:
        return prior

    direction = Direction.LONG if position.direction == "LONG" else Direction.SHORT
    avg_entry = float(position.entry_price)
    stop = float(position.stop_price) if position.stop_price is not None else avg_entry
    open_notional = float(position.notional or (open_qty * avg_entry))

    spread_bps, slip_bps = _friction(profile, position.symbol)
    # Same fill path as open — no silent fallback on failure.
    fill = apply_entry_friction(
        price,
        direction=position.direction,
        spread_bps=spread_bps,
        slippage_bps=slip_bps,
    )

    equity = estimate_equity(session, portfolio)
    requested = cap_add_by_notional_equity(
        open_notional=open_notional,
        requested_add_qty=float(initial_qty) * float(add_fraction),
        fill_price=float(fill),
        equity=float(equity),
        max_exposure=float(max_exposure),
    )
    if requested <= 1e-15:
        return None

    actual, new_avg, new_stop, new_qty, clamped = apply_reinforce_add(
        direction=direction,
        avg_entry=avg_entry,
        qty=open_qty,
        stop=stop,
        add_price=float(fill),
        requested_add=requested,
        initial_risk=float(initial_risk),
        policy=risk_policy if risk_policy in ("tighten_stop", "reduce_qty") else "tighten_stop",
    )
    if actual <= 1e-15:
        return None

    add_notional = actual * float(fill)
    # Re-check equity cap on actual (risk clamp may have shrunk qty).
    if open_notional + add_notional > float(max_exposure) * float(equity) + 1e-6:
        return None
    fee = _commission(profile, add_notional, actual, position.symbol)
    if add_notional + fee > float(portfolio.cash) + 1e-9:
        return None  # cash/margin gate — refuse, do not partial-fill silently

    coid = paper_orders.client_order_id_reinforce(position.id, seq)
    order = paper_orders.create_order(
        session,
        portfolio_id=portfolio.id,
        client_order_id=coid,
        position_id=position.id,
        symbol=position.symbol,
        timeframe=position.timeframe,
        side="BUY" if position.direction == "LONG" else "SELL",
        order_type="LIMIT",
        requested_price=price,
        qty=actual,
        notional=add_notional,
        fee=fee,
        spread_bps=spread_bps,
        slippage_bps=slip_bps,
        reason=reason,
        at=now,
    )
    if order.status in paper_orders.TERMINAL and order.status != paper_orders.FILLED:
        return None
    if order.status != paper_orders.FILLED:
        paper_orders.submit_ack_fill_market(
            session,
            order,
            filled_price=float(fill),
            filled_qty=actual,
            fee=fee,
            notional=add_notional,
            reason=reason,
            at=now,
        )
    if order.status != paper_orders.FILLED:
        return None

    cash_before = portfolio.cash
    portfolio.cash -= add_notional + fee
    portfolio.updated_at = now
    cash_delta = portfolio.cash - cash_before

    ledger_db.guarded(
        session,
        portfolio.id,
        position.id,
        "reinforce",
        lambda: ledger_db.post(
            session,
            portfolio.id,
            key,
            now,
            [
                Leg(
                    portfolio.currency,
                    ledger_db.to_decimal(cash_delta + fee),
                    Cause.EXECUTION,
                    f"reinforce {position.symbol} @ {r_multiple}R",
                ),
                Leg(
                    portfolio.currency,
                    -ledger_db.to_decimal(fee),
                    Cause.COMMISSION,
                    "reinforce entry commission",
                ),
            ],
            ref=position.id,
        ),
    )

    position.qty = new_qty
    position.entry_price = new_avg
    position.notional = new_qty * new_avg
    position.entry_fee = float(position.entry_fee or 0.0) + fee
    position.stop_price = new_stop
    position.risk_amount = open_risk(direction, new_avg, new_stop, new_qty)
    position.updated_at = now

    row = PaperReinforceAdd(
        portfolio_id=portfolio.id,
        position_id=position.id,
        seq=seq,
        key=key,
        r_multiple=float(r_multiple),
        fraction=float(add_fraction),
        qty=actual,
        price=float(fill),
        fee=fee,
        stop_after=new_stop,
        avg_entry_after=new_avg,
        open_risk_after=open_risk(direction, new_avg, new_stop, new_qty),
        clamped=clamped or actual + 1e-12 < requested,
        time_ms=ts_ms,
        created_at=now,
    )
    session.add(row)
    _journal(
        session,
        portfolio_id=portfolio.id,
        position_id=position.id,
        event_type="REINFORCE",
        payload={
            "seq": seq,
            "r_multiple": r_multiple,
            "fraction": add_fraction,
            "qty": actual,
            "price": float(fill),
            "avg_entry": new_avg,
            "stop": new_stop,
            "open_risk": row.open_risk_after,
            "clamped": row.clamped,
            "signal": signal,
        },
    )
    session.flush()
    return row


def check_stop_or_tp(position: PaperPosition, price: float) -> str | None:
    if position.stop_price is None or position.take_profit_price is None:
        return None
    if position.direction == "LONG":
        if price <= position.stop_price:
            return "stop_hit"
        if price >= position.take_profit_price:
            return "take_profit_hit"
    else:
        if price >= position.stop_price:
            return "stop_hit"
        if price <= position.take_profit_price:
            return "take_profit_hit"
    return None


def update_excursions(position: PaperPosition, price: float) -> None:
    if position.highest_price_seen is None or price > position.highest_price_seen:
        position.highest_price_seen = price
    if position.lowest_price_seen is None or price < position.lowest_price_seen:
        position.lowest_price_seen = price

    if position.direction == "LONG":
        fav = (position.highest_price_seen / position.entry_price) - 1.0
        adv = (position.lowest_price_seen / position.entry_price) - 1.0
    else:
        # SHORT: favourable when price falls, adverse when it rises (vs entry).
        fav = short_pnl_pct(position.entry_price, position.lowest_price_seen)
        adv = short_pnl_pct(position.entry_price, position.highest_price_seen)

    position.mfe_pct = max(position.mfe_pct or 0.0, fav)
    position.mae_pct = min(position.mae_pct or 0.0, adv)


def estimate_equity(session: Session, portfolio: PaperPortfolio) -> float:
    """Cash + reserved open notionals (conservative, pre-mark)."""
    opens = session.execute(
        select(PaperPosition).where(
            PaperPosition.portfolio_id == portfolio.id,
            PaperPosition.status == "OPEN",
        )
    ).scalars().all()
    reserved = sum((p.notional or 0.0) for p in opens)
    return portfolio.cash + reserved


def portfolio_friction_bps(portfolio: PaperPortfolio, symbol: str) -> tuple[float, float]:
    """Public (spread_bps, slippage_bps) for protection ↔ broker fill parity."""
    return _friction(_profile(portfolio), symbol)


def snapshot_equity(
    session: Session,
    portfolio: PaperPortfolio,
    *,
    marks: dict[str, float] | None = None,
) -> PaperEquitySnapshot:
    marks = marks or {}
    opens = session.execute(
        select(PaperPosition).where(
            PaperPosition.portfolio_id == portfolio.id,
            PaperPosition.status == "OPEN",
        )
    ).scalars().all()

    positions_value = 0.0
    unrealized = 0.0
    for p in opens:
        key = f"{p.symbol}:{p.timeframe}"
        mark = marks.get(key, p.entry_price)
        if p.qty:
            update_excursions(p, mark)
            if p.direction == "LONG":
                positions_value += p.qty * mark
                unrealized += p.qty * (mark - p.entry_price)
            else:
                # short: value as residual margin notionally
                positions_value += p.notional or 0.0
                unrealized += p.qty * (p.entry_price - mark)

    equity = portfolio.cash + positions_value
    # peak from prior snapshots
    prior = session.execute(
        select(func.max(PaperEquitySnapshot.equity)).where(
            PaperEquitySnapshot.portfolio_id == portfolio.id
        )
    ).scalar_one()
    peak = max(float(prior or equity), equity, float(portfolio.initial_cash))
    dd = ((equity / peak) - 1.0) if peak > 0 else None

    snap = PaperEquitySnapshot(
        portfolio_id=portfolio.id,
        timestamp=datetime.now(timezone.utc),
        cash=portfolio.cash,
        positions_value=positions_value,
        equity=equity,
        realized_pnl=portfolio.realized_pnl,
        unrealized_pnl=unrealized,
        drawdown_pct=dd,
    )
    session.add(snap)
    return snap
