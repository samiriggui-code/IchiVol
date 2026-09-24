#!/usr/bin/env python3
"""One-off SHORT realized recalculation after T0-FIX-SHORT-FEE (b9f8421).

Positions CLOSED as SHORT *before* that fix stored ``realized_pnl`` without
subtracting ``entry_fee`` (open + any reinforce fees present on the row at
close). This script:

1. Counts CLOSED SHORT lots closed strictly before the fix deployment
   timestamp (``#51`` squash mergedAt).
2. Skips lots already corrected (journal event ``SHORT_FEE_RECALC``).
3. With ``--apply``, rewrites ``realized_pnl`` / portfolio ``realized_pnl``
   and appends an idempotent journal marker.

Dry-run by default. Never run as an Alembic migration.
**Do not** chain ``--apply`` in CI / auto paths.

Usage (from ichivol-app/engine)::

    PYTHONPATH=. python scripts/recalc_short_entry_fee.py
    PYTHONPATH=. python scripts/recalc_short_entry_fee.py --apply
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import PaperJournalEvent, PaperPortfolio, PaperPosition
from app.db.session import SessionLocal

# Squash merge of #51 on main — exact UTC instant from GitHub mergedAt.
FIX_ACTIVATED_AT = datetime(2026, 9, 24, 7, 2, 48, tzinfo=timezone.utc)
EVENT_TYPE = "SHORT_FEE_RECALC"


def _as_utc(t: datetime) -> datetime:
    if t.tzinfo is None:
        return t.replace(tzinfo=timezone.utc)
    return t.astimezone(timezone.utc)


def already_recalculated(session: Session, position_id: str) -> bool:
    row = session.execute(
        select(PaperJournalEvent.id)
        .where(
            PaperJournalEvent.position_id == position_id,
            PaperJournalEvent.event_type == EVENT_TYPE,
        )
        .limit(1)
    ).scalar_one_or_none()
    return row is not None


def select_candidates(
    session: Session,
    *,
    activated_at: datetime = FIX_ACTIVATED_AT,
) -> tuple[list[PaperPosition], int]:
    """Return (candidates, closed_short_total).

    Candidate = CLOSED SHORT with ``exit_time < activated_at``, entry fee > 0,
    and no prior ``SHORT_FEE_RECALC`` journal event.
    """
    activated_at = _as_utc(activated_at)
    closed = list(
        session.execute(
            select(PaperPosition).where(
                PaperPosition.direction == "SHORT",
                PaperPosition.status == "CLOSED",
            )
        ).scalars()
    )
    candidates: list[PaperPosition] = []
    for p in closed:
        if p.exit_time is None:
            continue
        if _as_utc(p.exit_time) >= activated_at:
            continue
        fee = float(p.entry_fee or p.initial_entry_fee or 0.0)
        if fee <= 0:
            continue
        if already_recalculated(session, p.id):
            continue
        candidates.append(p)
    return candidates, len(closed)


def apply_corrections(
    session: Session,
    candidates: list[PaperPosition],
    *,
    activated_at: datetime = FIX_ACTIVATED_AT,
) -> int:
    """Apply fee deduction once per position; journal ``SHORT_FEE_RECALC``.

    Returns number of positions corrected. Safe to call twice — second pass
    selects zero candidates when markers exist.
    """
    by_portfolio: dict[str, float] = {}
    now = datetime.now(timezone.utc)
    n = 0
    for p in candidates:
        if already_recalculated(session, p.id):
            continue
        fee = float(p.entry_fee or p.initial_entry_fee or 0.0)
        old = float(p.realized_pnl or 0.0)
        new = old - fee
        p.realized_pnl = new
        p.updated_at = now
        by_portfolio[p.portfolio_id] = by_portfolio.get(p.portfolio_id, 0.0) + (new - old)
        session.add(
            PaperJournalEvent(
                portfolio_id=p.portfolio_id,
                position_id=p.id,
                event_type=EVENT_TYPE,
                payload={
                    "old_realized_pnl": old,
                    "new_realized_pnl": new,
                    "entry_fee": fee,
                    "fix_activated_at": _as_utc(activated_at).isoformat(),
                },
                created_at=now,
            )
        )
        n += 1

    for pid, delta in by_portfolio.items():
        pf = session.get(PaperPortfolio, pid)
        if pf is None:
            continue
        pf.realized_pnl = float(pf.realized_pnl or 0.0) + delta
        pf.updated_at = now

    return n


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true", help="Write corrections (default: dry-run)")
    ap.add_argument(
        "--activated-at",
        default=FIX_ACTIVATED_AT.isoformat(),
        help="UTC datetime from which closes are assumed correct (ISO-8601)",
    )
    args = ap.parse_args()
    activated = datetime.fromisoformat(args.activated_at.replace("Z", "+00:00"))
    if activated.tzinfo is None:
        activated = activated.replace(tzinfo=timezone.utc)

    session = SessionLocal()
    try:
        candidates, closed_total = select_candidates(session, activated_at=activated)
        print(f"CLOSED_SHORT_TOTAL={closed_total}")
        print(f"CLOSED_SHORT_PRE_FIX_WITH_ENTRY_FEE={len(candidates)}")
        if not candidates:
            print("Nothing to recalculate.")
            return 0

        for p in candidates[:20]:
            fee = float(p.entry_fee or p.initial_entry_fee or 0.0)
            stored = float(p.realized_pnl or 0.0)
            print(
                f"  id={p.id} symbol={p.symbol} exit={_as_utc(p.exit_time).isoformat()} "
                f"entry_fee={fee:.6f} stored_realized={stored:.6f} "
                f"corrected≈{stored - fee:.6f}"
            )
        if len(candidates) > 20:
            print(f"  … {len(candidates) - 20} more")

        if not args.apply:
            print("Dry-run only. Pass --apply to write corrected realized_pnl.")
            return 0

        n = apply_corrections(session, candidates, activated_at=activated)
        session.commit()
        print(f"Applied corrections to {n} position(s).")
        return 0
    finally:
        session.close()


if __name__ == "__main__":
    raise SystemExit(main())
