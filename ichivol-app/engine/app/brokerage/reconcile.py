"""Ledger <-> portfolio cash reconciliation for every paper portfolio (read-only).

``python -m app.brokerage.reconcile`` prints one line per portfolio and exits 1 if any
portfolio is out of balance. Portfolios with no ledger rows yet are reported as
``no_ledger`` (they get an opening balance on their first transaction), not as errors.
"""

from __future__ import annotations

import sys

from sqlalchemy import select

from app.brokerage import persistence as ledger_db
from app.db.models import LedgerTransaction, PaperPortfolio


def reconcile_all(session) -> list[dict]:
    out = []
    for pf in session.execute(select(PaperPortfolio).order_by(PaperPortfolio.code)).scalars():
        has = session.execute(
            select(LedgerTransaction.id).where(LedgerTransaction.portfolio_id == pf.id).limit(1)
        ).first()
        if has is None:
            out.append({"code": pf.code, "status": "no_ledger", "cash": pf.cash, "diff": None})
            continue
        diff = ledger_db.reconcile_cash(session, pf)
        out.append({"code": pf.code, "status": "ok" if ledger_db.is_reconciled(session, pf) else "MISMATCH",
                    "cash": pf.cash, "diff": str(diff)})
    return out


if __name__ == "__main__":
    from app.db.session import SessionLocal

    s = SessionLocal()
    try:
        rows = reconcile_all(s)
    finally:
        s.close()
    for r in rows:
        print(f"{r['code']:26s} {r['status']:10s} cash={r['cash']:.4f} diff={r['diff']}")
    sys.exit(1 if any(r["status"] == "MISMATCH" for r in rows) else 0)
