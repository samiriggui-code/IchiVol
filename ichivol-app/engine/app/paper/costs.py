"""Cost & profit breakdown of a paper portfolio (read-only).

Identity used (all in the portfolio currency, USDT treated as EUR):

    net result   = equity - initial cash                      (what the account really gained or lost)
    commissions  = sum of order fees (entry + exit, open lots' entry fee included)
    friction     = sum over orders of qty * |filled price - requested price|   (spread + slippage, already
                   inside the fill prices -- counted once, never added to the commissions)
    gross result = net result + commissions + friction         (what the same trades would have made for free)

Open lots are valued at the last mark; their EXIT costs are not paid yet and are not included.
"""

from __future__ import annotations

from typing import Any, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import PaperOrder, PaperPortfolio, PaperPosition


def market_class(symbol: str) -> str:
    return "crypto" if symbol.endswith("USDT") else "autres marchés"


def compute_costs(
    session: Session, portfolio: PaperPortfolio, *, equity: float, open_positions: Sequence[PaperPosition] | None = None
) -> dict[str, Any]:
    orders = session.execute(
        select(PaperOrder).where(PaperOrder.portfolio_id == portfolio.id, PaperOrder.status == "FILLED")
    ).scalars().all()
    positions = session.execute(
        select(PaperPosition).where(PaperPosition.portfolio_id == portfolio.id, PaperPosition.qty.is_not(None))
    ).scalars().all()

    by_class: dict[str, dict[str, float]] = {}

    def bucket(symbol: str) -> dict[str, float]:
        return by_class.setdefault(market_class(symbol), {"commissions": 0.0, "friction": 0.0, "orders": 0, "traded": 0.0})

    commissions = friction = traded = 0.0
    for o in orders:
        fee = float(o.fee or 0.0)
        fr = float(o.qty or 0.0) * abs(float(o.filled_price or 0.0) - float(o.requested_price or 0.0))
        commissions += fee
        friction += fr
        traded += float(o.notional or 0.0)
        b = bucket(o.symbol)
        b["commissions"] += fee
        b["friction"] += fr
        b["orders"] += 1
        b["traded"] += float(o.notional or 0.0)

    closed = [p for p in positions if p.status == "CLOSED" and p.realized_pnl is not None]
    wins = [float(p.realized_pnl) for p in closed if float(p.realized_pnl) > 0]
    losses = [float(p.realized_pnl) for p in closed if float(p.realized_pnl) <= 0]
    initial = float(portfolio.initial_cash)
    net = equity - initial
    gross = net + commissions + friction
    opens = [p for p in positions if p.status == "OPEN"]
    return {
        "currency": portfolio.currency,
        "initial_cash": initial,
        "equity": equity,
        "gross_result": gross,
        "commissions": commissions,
        "spread_slippage": friction,
        "total_costs": commissions + friction,
        "net_result": net,
        "net_return_pct": (net / initial) if initial else None,
        "cost_share_of_gross_pct": ((commissions + friction) / abs(gross)) if gross else None,
        "orders": len(orders),
        "notional_traded": traded,
        "open_positions": len(opens),
        "invested_now": sum(float(p.notional or 0.0) for p in opens),
        "closed_trades": len(closed),
        "wins": len(wins),
        "losses": len(losses),
        "sum_wins": sum(wins),
        "sum_losses": sum(losses),
        "by_market": {
            k: {kk: round(vv, 4) for kk, vv in v.items()} | {"total_costs": round(v["commissions"] + v["friction"], 4)}
            for k, v in by_class.items()
        },
        "note": "Frais de sortie des positions ouvertes non inclus (pas encore payés). Écarts et glissement sont déjà dans les prix d'exécution.",
    }
