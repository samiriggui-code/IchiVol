"""Paper trading -- virtual positions only, opened/closed purely by reading
`pipeline.decision` over time (CDC V2, docs/CAHIER-DES-CHARGES.md §4,
approved 2026-09-16). Never a real order, never a broker, never real money
-- the mission's own "paper avant live" rule (§7). Asset-class agnostic:
`PaperPosition` has no exchange/provider column, only `symbol`/`timeframe`,
so a position opens identically whether the underlying pipeline decision
came from Binance, biquote (forex/métal/index/énergie), or Twelve Data
(equity) -- see app/api/routes.py::open_paper_position, whose crypto-only
guard was lifted 2026-09-16 once crypto paper proved stable ("paper
multi-classe", docs/CAHIER-DES-CHARGES.md §5 V2). Two independent tracks,
same open/close rules, different trigger:

- "auto_watchlist": app/screener/cache.py's background refresh calls
  `sync_auto_watchlist` after every scan, reusing the rows it already
  computed -- no extra fetch. One open position per (symbol, timeframe) at
  a time, `user_id` is always None ("what if I'd just followed the engine
  everywhere").
- "user_confirmed": opened on demand (app/api/routes.py, called by the
  server when a user hits "Confirmer" in the Journal) for that one
  (symbol, timeframe, user_id) -- "how did MY picks do".

Exit rule matches the pipeline's own "never flips, only downgrades" logic
(docs/TRADING_ARCHITECTURE_V2.md §7): a position closes the moment its
symbol's live decision no longer supports it -- either downgraded
(WATCH/NO_TRADE) or the pipeline's direction genuinely flipped. Either way
this closes the position; it is never auto-reversed into the new side.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import PaperPosition
from app.decision.pipeline import PipelineResult


def _direction_for(decision: str) -> str | None:
    if decision == "BUY":
        return "LONG"
    if decision == "SELL":
        return "SHORT"
    return None


def _get_open_position(
    session: Session, *, symbol: str, timeframe: str, source: str, user_id: str | None
) -> PaperPosition | None:
    return session.execute(
        select(PaperPosition).where(
            PaperPosition.symbol == symbol,
            PaperPosition.timeframe == timeframe,
            PaperPosition.source == source,
            PaperPosition.user_id == user_id,
            PaperPosition.status == "OPEN",
        )
    ).scalar_one_or_none()


def _close(position: PaperPosition, *, price: float, reason: str) -> None:
    position.status = "CLOSED"
    position.exit_time = datetime.now(timezone.utc)
    position.exit_price = price
    position.exit_reason = reason
    position.pnl_pct = (
        (price / position.entry_price) - 1.0
        if position.direction == "LONG"
        else (position.entry_price / price) - 1.0
    )


def _open(
    session: Session,
    *,
    symbol: str,
    timeframe: str,
    source: str,
    user_id: str | None,
    direction: str,
    price: float,
    decision: str,
) -> PaperPosition:
    position = PaperPosition(
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
) -> PaperPosition | None:
    """One symbol's worth of open/hold/close logic given its just-computed
    live pipeline result. Returns the position touched (opened or closed),
    or None if nothing changed this cycle (still flat, or held unchanged)."""
    existing = _get_open_position(
        session, symbol=symbol, timeframe=timeframe, source=source, user_id=user_id
    )
    direction = _direction_for(pipeline.decision)

    if existing is None:
        if direction is None:
            return None
        position = _open(
            session, symbol=symbol, timeframe=timeframe, source=source, user_id=user_id,
            direction=direction, price=price, decision=pipeline.decision,
        )
        session.flush()
        return position

    if direction == existing.direction:
        return None  # still open, still supported -- nothing to do

    reason = "pipeline_flipped" if direction is not None else "pipeline_downgraded"
    _close(existing, price=price, reason=reason)
    session.flush()
    return existing


def sync_auto_watchlist(session: Session, rows: Sequence) -> list[PaperPosition]:
    """`rows` is the same `list[ScreenerRow]` the screener cache just
    computed (app/screener/service.py::scan_watchlist) -- reused as-is."""
    touched = [
        result
        for row in rows
        if (
            result := sync_position(
                session, symbol=row.symbol, timeframe=row.timeframe, source="auto_watchlist",
                user_id=None, price=row.price, pipeline=row.pipeline,
            )
        )
        is not None
    ]
    session.commit()
    return touched


def open_user_confirmed(
    session: Session, *, symbol: str, timeframe: str, user_id: str, price: float, pipeline: PipelineResult
) -> PaperPosition | None:
    """Idempotent: returns the user's existing open position unchanged
    rather than duplicating it if one is already open for this symbol."""
    existing = _get_open_position(
        session, symbol=symbol, timeframe=timeframe, source="user_confirmed", user_id=user_id
    )
    if existing is not None:
        return existing

    direction = _direction_for(pipeline.decision)
    if direction is None:
        return None

    position = _open(
        session, symbol=symbol, timeframe=timeframe, source="user_confirmed", user_id=user_id,
        direction=direction, price=price, decision=pipeline.decision,
    )
    session.commit()
    return position


def close_manually(session: Session, position_id: str, *, price: float) -> PaperPosition | None:
    position = session.get(PaperPosition, position_id)
    if position is None or position.status != "OPEN":
        return None
    _close(position, price=price, reason="manual_close")
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
) -> list[PaperPosition]:
    stmt = select(PaperPosition).order_by(PaperPosition.entry_time.desc())
    if source is not None:
        stmt = stmt.where(PaperPosition.source == source)
    if user_id is not None:
        stmt = stmt.where(PaperPosition.user_id == user_id)
    if status is not None:
        stmt = stmt.where(PaperPosition.status == status)
    return list(session.execute(stmt).scalars().all())
