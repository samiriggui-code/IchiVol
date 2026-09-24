"""T13c — kill switch + daily loss lock (persisted, human reopen only).

Never auto-lifts. Blocks paper **entries** only (closes/protection still run).
T13d: arming cancels every non-terminal paper order (CANCELLED, reason kill_switch).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import PaperJournalEvent, PaperPortfolio
from app.paper.counters import REJECT_EVENT
from app.paper.gates import day_start_equity

KILL_ARMED_EVENT = "KILL_ARMED"
KILL_DISARMED_EVENT = "KILL_DISARMED"
DAILY_LOSS_LOCKED_EVENT = "DAILY_LOSS_LOCKED"
DAILY_LOSS_UNLOCKED_EVENT = "DAILY_LOSS_UNLOCKED"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _journal(session: Session, portfolio: PaperPortfolio, event_type: str, payload: dict[str, Any]) -> None:
    session.add(
        PaperJournalEvent(
            portfolio_id=portfolio.id,
            position_id=None,
            event_type=event_type,
            payload=payload,
            created_at=_now(),
        )
    )


def lock_status(portfolio: PaperPortfolio) -> dict[str, Any]:
    return {
        "kill_switch_armed": bool(getattr(portfolio, "kill_switch_armed", False)),
        "kill_switch_armed_at": (
            portfolio.kill_switch_armed_at.isoformat()
            if getattr(portfolio, "kill_switch_armed_at", None)
            else None
        ),
        "daily_loss_locked": bool(getattr(portfolio, "daily_loss_locked", False)),
        "daily_loss_locked_at": (
            portfolio.daily_loss_locked_at.isoformat()
            if getattr(portfolio, "daily_loss_locked_at", None)
            else None
        ),
        "entries_blocked": bool(
            getattr(portfolio, "kill_switch_armed", False)
            or getattr(portfolio, "daily_loss_locked", False)
        ),
    }


def arm_kill_switch(session: Session, portfolio: PaperPortfolio, *, confirm: bool) -> PaperPortfolio:
    if not confirm:
        raise ValueError("confirm_required")
    if portfolio.kill_switch_armed:
        return portfolio
    portfolio.kill_switch_armed = True
    portfolio.kill_switch_armed_at = _now()
    from app.paper import orders as paper_orders

    cancelled = paper_orders.cancel_non_terminal_for_portfolio(
        session, portfolio.id, reason="kill_switch", at=_now()
    )
    _journal(
        session,
        portfolio,
        KILL_ARMED_EVENT,
        {
            "confirm": True,
            "cancelled_order_ids": [o.id for o in cancelled],
            "cancelled_count": len(cancelled),
        },
    )
    session.flush()
    return portfolio


def disarm_kill_switch(session: Session, portfolio: PaperPortfolio, *, confirm: bool) -> PaperPortfolio:
    """Human-only reopen. Never called from timers or equity recovery."""
    if not confirm:
        raise ValueError("confirm_required")
    if not portfolio.kill_switch_armed:
        return portfolio
    portfolio.kill_switch_armed = False
    portfolio.kill_switch_armed_at = None
    _journal(session, portfolio, KILL_DISARMED_EVENT, {"confirm": True})
    session.flush()
    return portfolio


def unlock_daily_loss(session: Session, portfolio: PaperPortfolio, *, confirm: bool) -> PaperPortfolio:
    if not confirm:
        raise ValueError("confirm_required")
    if not portfolio.daily_loss_locked:
        return portfolio
    portfolio.daily_loss_locked = False
    portfolio.daily_loss_locked_at = None
    _journal(session, portfolio, DAILY_LOSS_UNLOCKED_EVENT, {"confirm": True})
    session.flush()
    return portfolio


def maybe_trip_daily_loss_lock(
    session: Session,
    portfolio: PaperPortfolio,
    equity: float,
    *,
    now: datetime | None = None,
) -> bool:
    """Latch daily_loss_locked when profile limit breached. Never auto-clears.

    Returns True if newly latched (or already locked).
    """
    if getattr(portfolio, "daily_loss_locked", False):
        return True
    profile = portfolio.strategy_profile or {}
    lim = profile.get("daily_loss_limit_pct")
    if not lim:
        return False
    start = day_start_equity(session, portfolio, now)
    if start > 0 and equity <= start * (1 - float(lim)):
        portfolio.daily_loss_locked = True
        portfolio.daily_loss_locked_at = _now()
        _journal(
            session,
            portfolio,
            DAILY_LOSS_LOCKED_EVENT,
            {
                "equity": equity,
                "day_start_equity": start,
                "daily_loss_limit_pct": float(lim),
            },
        )
        # Also mirror as SIGNAL_REJECTED-style audit for Risk tab
        session.add(
            PaperJournalEvent(
                portfolio_id=portfolio.id,
                position_id=None,
                event_type=REJECT_EVENT,
                payload={
                    "symbol": "*",
                    "timeframe": "*",
                    "reason": "daily_loss_halt",
                    "codes": ["daily_loss_halt"],
                    "latched": True,
                },
                created_at=_now(),
            )
        )
        session.flush()
        return True
    return False
