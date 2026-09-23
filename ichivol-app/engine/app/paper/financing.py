"""Overnight financing (swap) for paper CFD-style positions (T0-BROKER).

Crypto spot: default 0 bps/day. Non-crypto CFD symbols use
``financing_bps_per_day_by_symbol`` — ASSUMPTIONS documented alongside friction
tables in ``strategy_profiles``.

Applied once per position per UTC day via idempotent ledger key
``financing:{position_id}:{YYYY-MM-DD}``. No retroactive charges before
``FINANCING_ACTIVATED_ON`` (inclusive).
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.brokerage import persistence as ledger_db
from app.brokerage.ledger import Cause, Leg
from app.db.models import LedgerTransaction, PaperJournalEvent, PaperPortfolio, PaperPosition
from app.paper.broker import _profile
from app.paper.strategy_profiles import market_financing_bps_per_day

logger = logging.getLogger(__name__)

# Inclusive — charges only for calendar days on/after this date (UTC).
FINANCING_ACTIVATED_ON = date(2026, 9, 23)


def financing_bps_for(profile: dict[str, Any], symbol: str) -> float:
    table = profile.get("financing_bps_per_day_by_symbol") or {}
    if symbol in table:
        return float(table[symbol])
    if symbol.endswith("USDT"):
        return float(profile.get("financing_bps_per_day_crypto", 0.0))
    return float(profile.get("financing_bps_per_day_default", market_financing_bps_per_day(symbol)))


def _day_key(position_id: str, day: date) -> str:
    return f"financing:{position_id}:{day.isoformat()}"


def apply_daily_financing(
    session: Session,
    portfolio: PaperPortfolio,
    *,
    as_of: datetime | None = None,
    force_day: date | None = None,
) -> list[dict[str, Any]]:
    """Debit overnight financing for each OPEN lot (idempotent per position×day)."""
    now = as_of or datetime.now(timezone.utc)
    day = force_day or now.date()
    if day < FINANCING_ACTIVATED_ON:
        return []

    profile = _profile(portfolio)
    opens = list(
        session.execute(
            select(PaperPosition).where(
                PaperPosition.portfolio_id == portfolio.id,
                PaperPosition.status == "OPEN",
                PaperPosition.qty.is_not(None),
            )
        ).scalars()
    )
    applied: list[dict[str, Any]] = []
    ledger_db.guarded(
        session,
        portfolio.id,
        None,
        "opening",
        lambda: ledger_db.ensure_opening(session, portfolio, now),
    )

    for pos in opens:
        bps = financing_bps_for(profile, pos.symbol)
        if bps <= 0:
            continue
        notional = float(pos.notional or 0.0)
        if notional <= 0:
            continue
        charge = notional * (bps / 10_000.0)
        if charge <= 0:
            continue
        key = _day_key(pos.id, day)
        existing = session.execute(
            select(LedgerTransaction.id).where(
                LedgerTransaction.portfolio_id == portfolio.id,
                LedgerTransaction.key == key,
            )
        ).scalar_one_or_none()
        if existing is not None:
            continue

        def _post(c=charge, k=key, p=pos):
            return ledger_db.post(
                session,
                portfolio.id,
                k,
                now,
                [
                    Leg(
                        portfolio.currency,
                        -ledger_db.to_decimal(c),
                        Cause.FINANCING,
                        f"overnight financing {p.symbol} {day.isoformat()}",
                    )
                ],
                ref=p.id,
            )

        result = ledger_db.guarded(session, portfolio.id, pos.id, "financing", _post)
        if result is None:
            continue

        portfolio.cash = float(portfolio.cash) - charge
        session.add(
            PaperJournalEvent(
                portfolio_id=portfolio.id,
                position_id=pos.id,
                event_type="FINANCING",
                payload={
                    "day": day.isoformat(),
                    "bps": bps,
                    "notional": notional,
                    "charge": charge,
                    "symbol": pos.symbol,
                },
                created_at=now,
            )
        )
        portfolio.updated_at = now
        applied.append(
            {
                "position_id": pos.id,
                "symbol": pos.symbol,
                "day": day.isoformat(),
                "charge": charge,
                "bps": bps,
            }
        )
    if applied:
        session.flush()
    return applied


def financing_total_for_position(session: Session, position_id: str) -> float:
    """Sum of FINANCING journal charges for a position (positive cost)."""
    evs = session.execute(
        select(PaperJournalEvent).where(
            PaperJournalEvent.position_id == position_id,
            PaperJournalEvent.event_type == "FINANCING",
        )
    ).scalars().all()
    return sum(float((e.payload or {}).get("charge") or 0.0) for e in evs)


def financing_total_for_portfolio(session: Session, portfolio_id: str) -> float:
    evs = session.execute(
        select(PaperJournalEvent).where(
            PaperJournalEvent.portfolio_id == portfolio_id,
            PaperJournalEvent.event_type == "FINANCING",
        )
    ).scalars().all()
    return sum(float((e.payload or {}).get("charge") or 0.0) for e in evs)


def apply_financing_all_portfolios(session: Session, *, as_of: datetime | None = None) -> int:
    """Run daily financing on every active paper portfolio. Returns charge count."""
    portfolios = session.execute(
        select(PaperPortfolio).where(PaperPortfolio.is_active.is_(True))
    ).scalars().all()
    n = 0
    for pf in portfolios:
        n += len(apply_daily_financing(session, pf, as_of=as_of))
    if n:
        session.commit()
    return n
