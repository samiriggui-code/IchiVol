"""Virtual paper broker — fills, cash, stops/TP, journal. Never real orders."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import (
    PaperEquitySnapshot,
    PaperJournalEvent,
    PaperOrder,
    PaperPortfolio,
    PaperPosition,
)
from app.paper.risk import apply_exit_friction, size_position
from app.paper.strategy_profiles import BASELINE_PROFILE


def _profile(portfolio: PaperPortfolio) -> dict[str, Any]:
    return portfolio.strategy_profile or dict(BASELINE_PROFILE)


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
) -> PaperPosition | None:
    """Open a sized paper position. Returns None if risk/cash/caps block it."""
    profile = _profile(portfolio)
    max_open = int(profile.get("max_open_positions", 5))
    if _count_open(session, portfolio.id) >= max_open:
        return None

    equity = estimate_equity(session, portfolio)
    sized = size_position(
        equity=equity,
        cash=portfolio.cash,
        direction=direction,
        entry_price=price,
        stop_distance=stop_distance,
        risk_pct=float(profile.get("risk_pct", 0.01)),
        take_profit_r=float(profile.get("take_profit_r", 2.0)),
        max_notional_pct=float(profile.get("max_notional_pct", 0.25)),
        commission_bps=float(profile.get("commission_bps", 5.0)),
        spread_bps=float(profile.get("spread_bps", 2.0)),
        slippage_bps=float(profile.get("slippage_bps", 3.0)),
    )
    if sized is None:
        return None

    fee = sized.notional * (float(profile.get("commission_bps", 5.0)) / 10_000.0)
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

    side = "BUY" if direction == "LONG" else "SELL"
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
            spread_bps=float(profile.get("spread_bps", 2.0)),
            slippage_bps=float(profile.get("slippage_bps", 3.0)),
            status="FILLED",
            reason="open",
            created_at=now,
        )
    )
    portfolio.cash -= sized.notional + fee
    portfolio.updated_at = now
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
) -> PaperPosition:
    portfolio = session.get(PaperPortfolio, position.portfolio_id) if position.portfolio_id else None
    profile = _profile(portfolio) if portfolio is not None else dict(BASELINE_PROFILE)
    now = datetime.now(timezone.utc)

    exit_fill = price
    exit_fee = 0.0
    realized = None

    if position.qty and position.qty > 0 and portfolio is not None:
        exit_fill = apply_exit_friction(
            price,
            direction=position.direction,
            spread_bps=float(profile.get("spread_bps", 2.0)),
            slippage_bps=float(profile.get("slippage_bps", 3.0)),
        )
        exit_fee = (position.qty * exit_fill) * (
            float(profile.get("commission_bps", 5.0)) / 10_000.0
        )
        entry_notional = position.notional or 0.0
        if position.direction == "LONG":
            proceeds = position.qty * exit_fill
            realized = proceeds - exit_fee - entry_notional - (position.entry_fee or 0.0)
            portfolio.cash += proceeds - exit_fee
        else:
            pnl_pct_local = (position.entry_price / exit_fill) - 1.0
            realized = entry_notional * pnl_pct_local - exit_fee
            # Return reserved short margin + PnL
            portfolio.cash += entry_notional + realized
        portfolio.realized_pnl += realized
        portfolio.updated_at = now

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
                spread_bps=float(profile.get("spread_bps", 2.0)),
                slippage_bps=float(profile.get("slippage_bps", 3.0)),
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
    position.exit_fee = exit_fee
    position.realized_pnl = realized
    position.pnl_pct = (
        (exit_fill / position.entry_price) - 1.0
        if position.direction == "LONG"
        else (position.entry_price / exit_fill) - 1.0
    )
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
                "realized_pnl": realized,
            },
        )
    return position


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
        fav = (position.entry_price / position.lowest_price_seen) - 1.0
        adv = (position.entry_price / position.highest_price_seen) - 1.0

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
