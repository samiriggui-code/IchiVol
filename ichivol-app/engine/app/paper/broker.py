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
    PaperOrder,
    PaperPartialExit,
    PaperPortfolio,
    PaperPosition,
)
from app.brokerage import persistence as ledger_db
from app.brokerage.execution import fill_at_quote
from app.brokerage.fee_profiles import get_schedule
from app.brokerage.ledger import Cause, Leg
from app.market_data.contracts import ExecutionMode, Quote
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
                PaperPosition.status == "OPEN",
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
        notional=sized.notional,
        stop_price=sized.stop_price,
        take_profit_price=sized.take_profit_price,
        risk_pct=sized.risk_pct,
        risk_amount=sized.risk_amount,
        entry_fee=fee,
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

    session.add(
        PaperOrder(
            portfolio_id=portfolio.id,
            position_id=position.id,
            symbol=symbol,
            timeframe=timeframe,
            side=side,
            order_type="MARKET",
            requested_price=price,
            filled_price=sized.entry_fill,
            qty=sized.qty,
            notional=sized.notional,
            fee=fee,
            spread_bps=spread_bps,
            slippage_bps=slippage_bps,
            status="FILLED",
            reason="open",
            created_at=now,
        )
    )
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
    if position.status != "OPEN":
        return position  # replay/double close: no second credit, no second order
    if not math.isfinite(float(price)):
        raise ValueError(f"non-finite exit price: {price!r}")
    portfolio = session.get(PaperPortfolio, position.portfolio_id) if position.portfolio_id else None
    _lock_portfolio(session, portfolio)
    bind = session.get_bind()
    if portfolio is not None and bind is not None and bind.dialect.name == "postgresql":
        # Another transaction (auto loop / monitor) may have closed this lot while we waited for the
        # portfolio lock: reload it and re-check, otherwise cash would be credited twice.
        session.refresh(position)
        if position.status != "OPEN":
            return position
    profile = _profile(portfolio) if portfolio is not None else dict(BASELINE_PROFILE)
    now = at or datetime.now(timezone.utc)

    exit_fill = price
    exit_fee = 0.0
    realized = None
    close_exec = None

    if position.qty and position.qty > 0 and portfolio is not None:
        ledger_db.guarded(session, portfolio.id, position.id, "opening", lambda: ledger_db.ensure_opening(session, portfolio, now))
        cash_before = portfolio.cash
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
        exit_fee = _commission(profile, position.qty * exit_fill, position.qty, position.symbol)
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
            # Correct SHORT return (entry − exit) / entry — NOT entry/exit − 1.
            pnl_currency = short_realized_currency(position.qty, position.entry_price, exit_fill)
            slice_realized = pnl_currency - exit_fee - financing_paid
            # Return reserved short margin + PnL (financing already left cash day by day)
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

        session.add(
            PaperOrder(
                portfolio_id=portfolio.id,
                position_id=position.id,
                symbol=position.symbol,
                timeframe=position.timeframe,
                side="SELL" if position.direction == "LONG" else "BUY",
                order_type="MARKET",
                requested_price=price,
                filled_price=exit_fill,
                qty=position.qty,
                notional=position.qty * exit_fill,
                fee=exit_fee,
                spread_bps=exit_spread_bps,
                slippage_bps=exit_slip_bps,
                status="FILLED",
                reason=reason,
                created_at=now,
            )
        )

    position.status = "CLOSED"
    position.exit_time = now
    position.exit_price = exit_fill
    position.exit_reason = reason
    position.exit_signal = signal
    position.exit_fee = (position.exit_fee or 0.0) + exit_fee
    position.realized_pnl = realized if realized is not None else position.realized_pnl
    position.pnl_pct = (
        (exit_fill / position.entry_price) - 1.0
        if position.direction == "LONG"
        else short_pnl_pct(position.entry_price, exit_fill)
    )
    position.qty = 0.0
    position.notional = 0.0
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

    # Idempotent replay
    prior = session.execute(
        select(PaperPartialExit).where(
            PaperPartialExit.portfolio_id == portfolio.id,
            PaperPartialExit.key == key,
        )
    ).scalar_one_or_none()
    if prior is not None:
        return prior

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

    cash_before = portfolio.cash
    if position.direction == "LONG":
        proceeds = qty * exit_fill
        slice_realized = proceeds - exit_fee - entry_notional_share - entry_fee_share
        portfolio.cash += proceeds - exit_fee
    else:
        pnl_currency = short_realized_currency(qty, position.entry_price, exit_fill)
        slice_realized = pnl_currency - exit_fee
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

    session.add(
        PaperOrder(
            portfolio_id=portfolio.id,
            position_id=position.id,
            symbol=position.symbol,
            timeframe=position.timeframe,
            side="SELL" if position.direction == "LONG" else "BUY",
            order_type="LIMIT",
            requested_price=price,
            filled_price=exit_fill,
            qty=qty,
            notional=qty * exit_fill,
            fee=exit_fee,
            spread_bps=spread_bps,
            slippage_bps=slip_bps,
            status="FILLED",
            reason=reason,
            created_at=now,
        )
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

    if new_qty <= 1e-12:
        # Exact scale-out of remainder via partial steps — finalize as CLOSED.
        position.qty = 0.0
        position.notional = 0.0
        position.status = "CLOSED"
        position.exit_time = now
        position.exit_price = exit_fill
        position.exit_reason = reason
        position.exit_signal = signal
        position.pnl_pct = (
            (exit_fill / position.entry_price) - 1.0
            if position.direction == "LONG"
            else short_pnl_pct(position.entry_price, exit_fill)
        )
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
                "via": "partial_exhausted",
            },
        )

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
