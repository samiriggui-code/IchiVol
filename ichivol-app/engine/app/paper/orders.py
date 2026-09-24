"""T13d — Paper order lifecycle (state machine + single creation point).

Accounting (cash / ledger / fills) stays in ``paper.broker``. This module owns
status transitions, append-only events, client_order_id idempotence, and the
only production constructor for ``PaperOrder``.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import PaperOrder, PaperOrderEvent

# —— Status vocabulary ——
CREATED = "CREATED"
SUBMITTED = "SUBMITTED"
ACK = "ACK"
PARTIAL = "PARTIAL"
FILLED = "FILLED"
CANCELLED = "CANCELLED"
REJECTED = "REJECTED"
EXPIRED = "EXPIRED"
UNKNOWN = "UNKNOWN"

ALL_STATUSES: frozenset[str] = frozenset(
    {
        CREATED,
        SUBMITTED,
        ACK,
        PARTIAL,
        FILLED,
        CANCELLED,
        REJECTED,
        EXPIRED,
        UNKNOWN,
    }
)

TERMINAL: frozenset[str] = frozenset({FILLED, CANCELLED, REJECTED, EXPIRED})

# Declared legal transitions. Terminals have empty sets (immutable).
# UNKNOWN may only leave via reconciliation (explicit allowlist here).
TRANSITIONS: dict[str, frozenset[str]] = {
    CREATED: frozenset({SUBMITTED, CANCELLED, REJECTED, EXPIRED}),
    SUBMITTED: frozenset({ACK, CANCELLED, REJECTED, EXPIRED, UNKNOWN}),
    ACK: frozenset({PARTIAL, FILLED, CANCELLED, REJECTED, EXPIRED, UNKNOWN}),
    PARTIAL: frozenset({PARTIAL, FILLED, CANCELLED, REJECTED, EXPIRED, UNKNOWN}),
    UNKNOWN: frozenset({FILLED, CANCELLED, REJECTED}),
    FILLED: frozenset(),
    CANCELLED: frozenset(),
    REJECTED: frozenset(),
    EXPIRED: frozenset(),
}


class IllegalOrderTransition(ValueError):
    """Raised when a status change is not in the declared table."""

    def __init__(self, order_id: str, frm: str, to: str) -> None:
        self.order_id = order_id
        self.frm = frm
        self.to = to
        super().__init__(f"illegal transition {frm!r} → {to!r} on order {order_id}")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _next_seq(session: Session, order_id: str) -> int:
    last = session.execute(
        select(PaperOrderEvent.seq)
        .where(PaperOrderEvent.order_id == order_id)
        .order_by(PaperOrderEvent.seq.desc())
        .limit(1)
    ).scalar_one_or_none()
    return int(last or 0) + 1


def transition(
    session: Session,
    order: PaperOrder,
    to: str,
    *,
    reason: str | None = None,
    codes: list[str] | None = None,
    at: datetime | None = None,
) -> PaperOrderEvent:
    """Apply one legal status change and append an event. Terminals are immutable."""
    if to not in ALL_STATUSES:
        raise IllegalOrderTransition(order.id, order.status, to)
    frm = order.status
    if frm in TERMINAL:
        raise IllegalOrderTransition(order.id, frm, to)
    allowed = TRANSITIONS.get(frm, frozenset())
    if to not in allowed:
        raise IllegalOrderTransition(order.id, frm, to)
    when = at or _now()
    order.status = to
    ev = PaperOrderEvent(
        order_id=order.id,
        seq=_next_seq(session, order.id),
        from_status=frm,
        to_status=to,
        at=when,
        reason=reason,
        codes=list(codes or []),
    )
    session.add(ev)
    session.flush()
    return ev


def get_by_client_order_id(
    session: Session, portfolio_id: str, client_order_id: str
) -> PaperOrder | None:
    return session.execute(
        select(PaperOrder).where(
            PaperOrder.portfolio_id == portfolio_id,
            PaperOrder.client_order_id == client_order_id,
        )
    ).scalar_one_or_none()


def create_order(
    session: Session,
    *,
    portfolio_id: str,
    client_order_id: str,
    symbol: str,
    timeframe: str,
    side: str,
    order_type: str,
    requested_price: float,
    qty: float,
    notional: float,
    fee: float = 0.0,
    spread_bps: float = 0.0,
    slippage_bps: float = 0.0,
    reason: str | None = None,
    position_id: str | None = None,
    filled_price: float = 0.0,
    expires_at: datetime | None = None,
    intent_ref: str | None = None,
    at: datetime | None = None,
) -> PaperOrder:
    """Single production constructor. Idempotent on ``(portfolio_id, client_order_id)``."""
    existing = get_by_client_order_id(session, portfolio_id, client_order_id)
    if existing is not None:
        return existing

    when = at or _now()
    order = PaperOrder(
        portfolio_id=portfolio_id,
        position_id=position_id,
        symbol=symbol,
        timeframe=timeframe,
        side=side,
        order_type=order_type,
        requested_price=requested_price,
        filled_price=filled_price,
        qty=qty,
        notional=notional,
        fee=fee,
        spread_bps=spread_bps,
        slippage_bps=slippage_bps,
        status=CREATED,
        reason=reason,
        created_at=when,
        client_order_id=client_order_id,
        filled_qty=0.0,
        avg_fill_price=None,
        expires_at=expires_at,
        intent_ref=intent_ref,
    )
    session.add(order)
    session.flush()
    # Birth event: synthetic from None → CREATED for audit trail
    session.add(
        PaperOrderEvent(
            order_id=order.id,
            seq=1,
            from_status=None,
            to_status=CREATED,
            at=when,
            reason=reason or "created",
            codes=[],
        )
    )
    session.flush()
    return order


def submit_ack_fill_market(
    session: Session,
    order: PaperOrder,
    *,
    filled_price: float,
    filled_qty: float,
    fee: float,
    notional: float,
    reason: str | None = None,
    at: datetime | None = None,
) -> PaperOrder:
    """Paper market happy path in one transaction: CREATED→SUBMITTED→ACK→FILLED.

    No PARTIAL simulation (no invented liquidity). Caller applies cash/ledger
    only when this returns a newly FILLED order (check status + prior state).
    """
    when = at or _now()
    if order.status == FILLED:
        return order
    if order.status == CREATED:
        transition(session, order, SUBMITTED, reason="submit", at=when)
    if order.status == SUBMITTED:
        transition(session, order, ACK, reason="ack", at=when)
    if order.status == ACK:
        order.filled_price = float(filled_price)
        order.filled_qty = float(filled_qty)
        order.avg_fill_price = float(filled_price)
        order.fee = float(fee)
        order.notional = float(notional)
        if reason is not None:
            order.reason = reason
        transition(session, order, FILLED, reason=reason or "filled", at=when)
    return order


def reject_order(
    session: Session,
    order: PaperOrder,
    *,
    reason: str,
    codes: list[str] | None = None,
    at: datetime | None = None,
) -> PaperOrder:
    if order.status in TERMINAL:
        return order
    # Drive toward REJECTED through current state edges
    when = at or _now()
    if order.status == CREATED:
        transition(session, order, REJECTED, reason=reason, codes=codes, at=when)
    elif order.status in (SUBMITTED, ACK, PARTIAL, UNKNOWN):
        transition(session, order, REJECTED, reason=reason, codes=codes, at=when)
    return order


def cancel_order(
    session: Session,
    order: PaperOrder,
    *,
    reason: str,
    codes: list[str] | None = None,
    at: datetime | None = None,
) -> PaperOrder:
    if order.status in TERMINAL:
        return order
    when = at or _now()
    transition(session, order, CANCELLED, reason=reason, codes=codes, at=when)
    return order


def expire_order(
    session: Session,
    order: PaperOrder,
    *,
    reason: str = "expired",
    at: datetime | None = None,
) -> PaperOrder:
    if order.status in TERMINAL:
        return order
    when = at or _now()
    transition(session, order, EXPIRED, reason=reason, at=when)
    return order


def mark_unknown(
    session: Session,
    order: PaperOrder,
    *,
    reason: str = "stale",
    at: datetime | None = None,
) -> PaperOrder:
    if order.status in TERMINAL or order.status == UNKNOWN:
        return order
    when = at or _now()
    transition(session, order, UNKNOWN, reason=reason, codes=["stale"], at=when)
    return order


def resolve_unknown(
    session: Session,
    order: PaperOrder,
    *,
    to: str,
    reason: str,
    codes: list[str] | None = None,
    at: datetime | None = None,
) -> PaperOrder:
    """Reconciliation-only exit from UNKNOWN → FILLED | CANCELLED | REJECTED."""
    if order.status != UNKNOWN:
        raise IllegalOrderTransition(order.id, order.status, to)
    if to not in (FILLED, CANCELLED, REJECTED):
        raise IllegalOrderTransition(order.id, UNKNOWN, to)
    when = at or _now()
    if to == FILLED:
        if not order.filled_qty:
            order.filled_qty = float(order.qty or 0.0)
        if order.avg_fill_price is None and order.filled_price is not None:
            order.avg_fill_price = float(order.filled_price)
    transition(session, order, to, reason=reason, codes=codes, at=when)
    return order


def cancel_non_terminal_for_portfolio(
    session: Session,
    portfolio_id: str,
    *,
    reason: str = "kill_switch",
    at: datetime | None = None,
) -> list[PaperOrder]:
    """Cancel every non-terminal order (T13c arm hook)."""
    rows = list(
        session.execute(
            select(PaperOrder).where(PaperOrder.portfolio_id == portfolio_id)
        ).scalars()
    )
    cancelled: list[PaperOrder] = []
    when = at or _now()
    for o in rows:
        if o.status in TERMINAL:
            continue
        cancel_order(session, o, reason=reason, codes=["kill_switch"], at=when)
        cancelled.append(o)
    return cancelled


def client_order_id_open(
    *,
    portfolio_id: str,
    symbol: str,
    timeframe: str,
    side: str,
    bar_key: str,
) -> str:
    return f"open:{portfolio_id}:{symbol}:{timeframe}:{bar_key}:{side}"


def client_order_id_close(position_id: str, attempt: int) -> str:
    return f"close:{position_id}:{int(attempt)}"


def client_order_id_partial(position_id: str, seq: int) -> str:
    return f"partial:{position_id}:{seq}"


def client_order_id_reinforce(position_id: str, seq: int) -> str:
    return f"reinforce:{position_id}:{seq}"


def resolve_close_client_order_id(
    session: Session, portfolio_id: str, position_id: str
) -> tuple[str, PaperOrder | None]:
    """Pick close client_order_id for this position.

    - Existing FILLED → resume (idempotent, no 2nd fill).
    - Existing non-terminal → resume same attempt.
    - Else next attempt ``close:{pid}:{n}`` after REJECTED/CANCELLED/EXPIRED.
    """
    rows = list(
        session.execute(
            select(PaperOrder).where(
                PaperOrder.portfolio_id == portfolio_id,
                PaperOrder.position_id == position_id,
            )
        ).scalars()
    )
    matched: list[PaperOrder] = []
    for o in rows:
        coid = o.client_order_id or ""
        if coid == f"close:{position_id}" or coid.startswith(f"close:{position_id}:"):
            matched.append(o)
    for o in matched:
        if o.status == FILLED:
            return o.client_order_id or client_order_id_close(position_id, 1), o
    for o in matched:
        if o.status not in TERMINAL:
            return o.client_order_id or client_order_id_close(position_id, 1), o
    attempts: list[int] = []
    for o in matched:
        coid = o.client_order_id or ""
        if coid.startswith(f"close:{position_id}:"):
            try:
                attempts.append(int(coid.rsplit(":", 1)[-1]))
            except ValueError:
                attempts.append(1)
        elif coid == f"close:{position_id}":
            attempts.append(1)
    nxt = (max(attempts) if attempts else 0) + 1
    return client_order_id_close(position_id, nxt), None


def resolve_open_bar_key(
    signal: dict[str, Any] | None,
    *,
    decision_id: str | None = None,
    intent_ref: str | None = None,
) -> str | None:
    """Bar identity for open idempotence. No wall-clock fallback.

    Prefer ``bar_time`` (and aliases) from signal; else ``decision:{id}`` /
    ``intent:{ref}``. ``None`` → caller must refuse with ``no_bar_key``.
    """
    if signal:
        for k in ("bar_time", "candle_time", "time", "t", "time_ms", "closed_at"):
            v = signal.get(k)
            if v is None or v == "":
                continue
            return str(v)
        iref = signal.get("intent_ref")
        if iref:
            return f"intent:{iref}"
    if decision_id:
        return f"decision:{decision_id}"
    if intent_ref:
        return f"intent:{intent_ref}"
    return None


def list_events(session: Session, order_id: str) -> list[PaperOrderEvent]:
    return list(
        session.execute(
            select(PaperOrderEvent)
            .where(PaperOrderEvent.order_id == order_id)
            .order_by(PaperOrderEvent.seq.asc())
        ).scalars()
    )
