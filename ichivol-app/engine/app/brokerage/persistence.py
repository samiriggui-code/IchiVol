"""DB-backed ledger posting for paper portfolios (idempotent, append-only)."""

from __future__ import annotations

import math
from datetime import datetime, timezone
from decimal import Decimal
from typing import Callable, TypeVar

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.brokerage.ledger import Cause, DuplicateConflict, Leg
from app.db.models import LedgerLeg, LedgerTransaction, PaperJournalEvent, PaperPortfolio

T = TypeVar("T")

_TOLERANCE = Decimal("0.0001")


def to_decimal(value: float | None, places: int = 8) -> Decimal:
    """Float -> Decimal via repr, rounded, so float noise does not leak in. NaN/inf are refused."""
    v = float(value or 0.0)
    if not math.isfinite(v):
        raise ValueError(f"non-finite amount: {v!r}")
    return round(Decimal(repr(v)), places)


def guarded(session: Session, portfolio_id: str | None, position_id: str | None, what: str, fn: Callable[[], T]) -> T | None:
    """Run ledger writes in a SAVEPOINT. A ledger failure (missing table, conflict, bad value) must
    never abort the trade itself: it is recorded as a LEDGER_ERROR journal event and surfaced by
    ``python -m app.brokerage.reconcile`` instead."""
    try:
        with session.begin_nested():
            return fn()
    except Exception as exc:  # noqa: BLE001
        session.add(
            PaperJournalEvent(
                portfolio_id=portfolio_id, position_id=position_id, event_type="LEDGER_ERROR",
                payload={"what": what, "error": repr(exc)[:300]}, created_at=datetime.now(timezone.utc),
            )
        )
        return None


def post(
    session: Session,
    portfolio_id: str,
    key: str,
    ts: datetime,
    legs: list[Leg],
    ref: str | None = None,
) -> LedgerTransaction:
    existing = session.execute(
        select(LedgerTransaction).where(
            LedgerTransaction.portfolio_id == portfolio_id, LedgerTransaction.key == key
        )
    ).scalar_one_or_none()
    if existing is not None:
        stored = [(l.currency, Decimal(l.amount), l.cause) for l in existing.legs]
        wanted = [(l.currency, l.amount, l.cause.value) for l in legs]
        if stored != wanted or existing.ref != ref:
            raise DuplicateConflict(key)
        return existing
    tx = LedgerTransaction(portfolio_id=portfolio_id, key=key, ref=ref, ts=ts)
    tx.legs = [
        LedgerLeg(seq=i, currency=l.currency, amount=l.amount, cause=l.cause.value, memo=l.memo)
        for i, l in enumerate(legs)
    ]
    session.add(tx)
    session.flush()
    return tx


def ensure_opening(session: Session, portfolio: PaperPortfolio, ts: datetime) -> None:
    """Seed the ledger with the portfolio's current cash the first time it is used.

    A portfolio already carrying history gets a CORRECTION-caused opening
    balance (explicit, never disguised as a deposit)."""
    has_any = session.execute(
        select(LedgerTransaction.id).where(LedgerTransaction.portfolio_id == portfolio.id).limit(1)
    ).first()
    if has_any is not None:
        return
    fresh = abs(portfolio.cash - portfolio.initial_cash) < 1e-9 and portfolio.realized_pnl == 0
    cause = Cause.DEPOSIT if fresh else Cause.CORRECTION
    memo = "initial capital" if fresh else "opening balance at ledger start (pre-ledger history)"
    post(
        session,
        portfolio.id,
        f"opening:{portfolio.id}",
        ts,
        [Leg(portfolio.currency, to_decimal(portfolio.cash), cause, memo)],
    )


def balances(session: Session, portfolio_id: str) -> dict[str, Decimal]:
    out: dict[str, Decimal] = {}
    rows = session.execute(
        select(LedgerLeg.currency, LedgerLeg.amount)
        .join(LedgerTransaction, LedgerLeg.transaction_id == LedgerTransaction.id)
        .where(LedgerTransaction.portfolio_id == portfolio_id)
    ).all()
    for cur, amt in rows:
        out[cur] = out.get(cur, Decimal(0)) + Decimal(amt)
    return out


def reconcile_cash(session: Session, portfolio: PaperPortfolio) -> Decimal:
    """Ledger balance minus the portfolio's cash field, in portfolio currency.
    Should be ~0; anything beyond tolerance is a bookkeeping defect."""
    return balances(session, portfolio.id).get(portfolio.currency, Decimal(0)) - to_decimal(portfolio.cash)


def is_reconciled(session: Session, portfolio: PaperPortfolio) -> bool:
    return abs(reconcile_cash(session, portfolio)) <= _TOLERANCE
