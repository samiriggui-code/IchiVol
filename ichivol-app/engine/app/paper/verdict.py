"""Live test progress and pre-registered verdict for a paper portfolio (read-only).

The criteria were fixed BEFORE any live result (docs/PLAN-SUIVI-EN-AVANT-2026-09-20.md) so the system cannot be judged
on a lucky week: enough trades AND enough time, then net > 0 even without the 3 best trades, positive in at least 2
of 3 consecutive sub-periods, and a drawdown under 15 %. Until the sample is large enough the verdict is
"insufficient evidence" -- never a forecast, never annualised.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import PaperEquitySnapshot, PaperPortfolio, PaperPosition

MIN_TRADES = 150
MIN_DAYS = 56
MAX_DD = 0.15


def compute_progress(session: Session, portfolio: PaperPortfolio, *, equity: float, now: datetime | None = None) -> dict[str, Any]:
    now = now or datetime.now(timezone.utc)
    started = portfolio.started_at if portfolio.started_at.tzinfo else portfolio.started_at.replace(tzinfo=timezone.utc)
    days = max(0.0, (now - started).total_seconds() / 86400)
    closed = session.execute(
        select(PaperPosition)
        .where(PaperPosition.portfolio_id == portfolio.id, PaperPosition.status == "CLOSED", PaperPosition.qty.is_not(None),
               PaperPosition.realized_pnl.is_not(None), PaperPosition.exit_time.is_not(None))
        .order_by(PaperPosition.exit_time)
    ).scalars().all()
    nets = [float(p.realized_pnl) for p in closed]
    n = len(nets)
    net_closed = sum(nets)
    top3 = sum(sorted(nets, reverse=True)[:3])
    thirds: list[float] = []
    if n >= 3:
        t0 = closed[0].exit_time.timestamp()
        t1 = closed[-1].exit_time.timestamp()
        step = (t1 - t0) / 3 or 1.0
        for i in range(3):
            lo, hi = t0 + step * i, t0 + step * (i + 1)
            thirds.append(sum(float(p.realized_pnl) for p in closed if lo <= p.exit_time.timestamp() <= hi
                              and (i == 2 or p.exit_time.timestamp() < hi)))
    snaps = session.execute(
        select(PaperEquitySnapshot.equity).where(PaperEquitySnapshot.portfolio_id == portfolio.id).order_by(PaperEquitySnapshot.timestamp)
    ).scalars().all()
    peak, dd = float(portfolio.initial_cash), 0.0
    for e in snaps:
        peak = max(peak, float(e))
        dd = min(dd, float(e) / peak - 1.0)
    rate = n / days if days > 0.25 else None
    eta_days = ((MIN_TRADES - n) / rate) if rate and rate > 0 and n < MIN_TRADES else 0.0 if n >= MIN_TRADES else None
    enough = n >= MIN_TRADES and days >= MIN_DAYS
    checks = {
        "net_positive": (equity - float(portfolio.initial_cash)) > 0,
        "net_without_top3_positive": (net_closed - top3) > 0,
        "two_of_three_periods_positive": sum(1 for x in thirds if x > 0) >= 2 if thirds else False,
        "drawdown_under_15pct": abs(dd) < MAX_DD,
    }
    if not enough:
        verdict, label = "insufficient", "Pas assez de données pour juger"
    elif all(checks.values()):
        verdict, label = "candidate", "Système validé sur cet échantillon"
    else:
        verdict, label = "not_retained", "Système non validé sur cet échantillon"
    return {
        "days": round(days, 1), "min_days": MIN_DAYS, "closed_trades": n, "min_trades": MIN_TRADES,
        "trades_per_day": round(rate, 2) if rate else None,
        "eta_days_to_min_trades": round(eta_days, 1) if eta_days is not None else None,
        "progress_pct": round(min(1.0, min(n / MIN_TRADES, days / MIN_DAYS)) * 100, 1),
        "net_realized_closed": round(net_closed, 2), "top3_gains": round(top3, 2),
        "net_without_top3": round(net_closed - top3, 2), "sub_period_net": [round(x, 2) for x in thirds],
        "max_drawdown_pct": round(dd * 100, 2), "checks": checks, "verdict": verdict, "verdict_label": label,
        "rules": "150 transactions clôturées ET 8 semaines ; puis net > 0 (y compris sans les 3 meilleures transactions), "
                 "positif sur au moins 2 des 3 sous-périodes, drawdown < 15 %. Aucune annualisation.",
    }
