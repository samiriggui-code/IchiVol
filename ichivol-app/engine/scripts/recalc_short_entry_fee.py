#!/usr/bin/env python3
"""One-off SHORT realized recalculation after T0-FIX-SHORT-FEE (b9f8421).

Positions CLOSED as SHORT *before* that fix stored ``realized_pnl`` without
subtracting ``entry_fee`` (open + any reinforce fees present on the row at
close). This script:

1. Counts CLOSED SHORT lots (with optional ``--since`` / ``--until``).
2. With ``--apply``, rewrites ``realized_pnl`` / portfolio ``realized_pnl``
   for rows closed before the fix activation date (default 2026-09-24).

Dry-run by default. Never run as an Alembic migration.

Usage (from ichivol-app/engine)::

    PYTHONPATH=. python scripts/recalc_short_entry_fee.py
    PYTHONPATH=. python scripts/recalc_short_entry_fee.py --apply
"""

from __future__ import annotations

import argparse
from datetime import date, datetime, timezone

from sqlalchemy import select

from app.db.models import PaperPortfolio, PaperPosition
from app.db.session import SessionLocal

# Squash merge of #51 on main — lots closed on/after this UTC day are correct.
FIX_ACTIVATED_ON = date(2026, 9, 24)


def _exit_day(pos: PaperPosition) -> date | None:
    if pos.exit_time is None:
        return None
    t = pos.exit_time
    if t.tzinfo is None:
        t = t.replace(tzinfo=timezone.utc)
    return t.astimezone(timezone.utc).date()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true", help="Write corrections (default: dry-run)")
    ap.add_argument(
        "--activated-on",
        default=FIX_ACTIVATED_ON.isoformat(),
        help="UTC date from which closes are assumed correct (YYYY-MM-DD)",
    )
    args = ap.parse_args()
    activated = date.fromisoformat(args.activated_on)

    session = SessionLocal()
    try:
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
            day = _exit_day(p)
            if day is None or day >= activated:
                continue
            fee = float(p.entry_fee or p.initial_entry_fee or 0.0)
            if fee <= 0:
                continue
            candidates.append(p)

        print(f"CLOSED_SHORT_TOTAL={len(closed)}")
        print(f"CLOSED_SHORT_PRE_FIX_WITH_ENTRY_FEE={len(candidates)}")
        if not candidates:
            print("Nothing to recalculate.")
            return 0

        for p in candidates[:20]:
            fee = float(p.entry_fee or p.initial_entry_fee or 0.0)
            stored = float(p.realized_pnl or 0.0)
            print(
                f"  id={p.id} symbol={p.symbol} exit={_exit_day(p)} "
                f"entry_fee={fee:.6f} stored_realized={stored:.6f} "
                f"corrected≈{stored - fee:.6f}"
            )
        if len(candidates) > 20:
            print(f"  … {len(candidates) - 20} more")

        if not args.apply:
            print("Dry-run only. Pass --apply to write corrected realized_pnl.")
            return 0

        by_portfolio: dict[str, float] = {}
        for p in candidates:
            fee = float(p.entry_fee or p.initial_entry_fee or 0.0)
            old = float(p.realized_pnl or 0.0)
            new = old - fee
            p.realized_pnl = new
            by_portfolio[p.portfolio_id] = by_portfolio.get(p.portfolio_id, 0.0) + (new - old)
            p.updated_at = datetime.now(timezone.utc)

        for pid, delta in by_portfolio.items():
            pf = session.get(PaperPortfolio, pid)
            if pf is None:
                continue
            pf.realized_pnl = float(pf.realized_pnl or 0.0) + delta
            pf.updated_at = datetime.now(timezone.utc)

        session.commit()
        print(f"Applied corrections to {len(candidates)} position(s).")
        return 0
    finally:
        session.close()


if __name__ == "__main__":
    raise SystemExit(main())
