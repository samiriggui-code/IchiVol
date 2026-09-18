"""Paper trading performance — trade % metrics + capital/equity metrics."""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass
from typing import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import PaperEquitySnapshot, PaperPortfolio, PaperPosition


@dataclass(frozen=True)
class PaperPerformance:
    num_closed_trades: int
    num_open_positions: int
    total_return: float | None
    win_rate: float | None
    profit_factor: float | None
    expectancy: float | None
    avg_holding_hours: float | None
    best_trade_pct: float | None
    worst_trade_pct: float | None
    # Capital-aware (Phase 1 broker) — None when no portfolio / no sized trades
    initial_cash: float | None = None
    cash: float | None = None
    equity: float | None = None
    realized_pnl: float | None = None
    unrealized_pnl: float | None = None
    max_drawdown: float | None = None
    expectancy_eur: float | None = None
    valuation_mode: str | None = None


_EMPTY = PaperPerformance(
    num_closed_trades=0,
    num_open_positions=0,
    total_return=None,
    win_rate=None,
    profit_factor=None,
    expectancy=None,
    avg_holding_hours=None,
    best_trade_pct=None,
    worst_trade_pct=None,
)


def compute_performance(positions: Sequence[PaperPosition]) -> PaperPerformance:
    closed = [p for p in positions if p.status == "CLOSED" and p.pnl_pct is not None]
    open_count = sum(1 for p in positions if p.status == "OPEN")

    if not closed:
        return (
            _EMPTY
            if open_count == 0
            else PaperPerformance(
                num_closed_trades=0,
                num_open_positions=open_count,
                total_return=None,
                win_rate=None,
                profit_factor=None,
                expectancy=None,
                avg_holding_hours=None,
                best_trade_pct=None,
                worst_trade_pct=None,
            )
        )

    pnls = [p.pnl_pct for p in closed]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p <= 0]
    total_return = math.prod(1 + p for p in pnls) - 1
    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))
    profit_factor = (
        (gross_profit / gross_loss) if gross_loss > 0 else (math.inf if gross_profit > 0 else None)
    )
    holding_hours = [
        (p.exit_time - p.entry_time).total_seconds() / 3600.0
        for p in closed
        if p.exit_time is not None
    ]
    eur_pnls = [p.realized_pnl for p in closed if p.realized_pnl is not None]

    return PaperPerformance(
        num_closed_trades=len(closed),
        num_open_positions=open_count,
        total_return=total_return,
        win_rate=len(wins) / len(closed),
        profit_factor=profit_factor,
        expectancy=statistics.mean(pnls),
        avg_holding_hours=statistics.mean(holding_hours) if holding_hours else None,
        best_trade_pct=max(pnls),
        worst_trade_pct=min(pnls),
        expectancy_eur=statistics.mean(eur_pnls) if eur_pnls else None,
    )


def compute_portfolio_performance(
    session: Session, portfolio: PaperPortfolio, positions: Sequence[PaperPosition]
) -> PaperPerformance:
    base = compute_performance(positions)
    snaps = session.execute(
        select(PaperEquitySnapshot)
        .where(PaperEquitySnapshot.portfolio_id == portfolio.id)
        .order_by(PaperEquitySnapshot.timestamp.asc())
    ).scalars().all()

    equity = snaps[-1].equity if snaps else (portfolio.cash + portfolio.initial_cash - portfolio.cash)
    # Prefer latest snapshot; else cash + reserved notionals approximation
    if snaps:
        equity = snaps[-1].equity
        unrealized = snaps[-1].unrealized_pnl
        max_dd = min((s.drawdown_pct for s in snaps if s.drawdown_pct is not None), default=None)
    else:
        reserved = sum((p.notional or 0.0) for p in positions if p.status == "OPEN")
        equity = portfolio.cash + reserved
        unrealized = None
        max_dd = None

    return PaperPerformance(
        num_closed_trades=base.num_closed_trades,
        num_open_positions=base.num_open_positions,
        total_return=(equity / portfolio.initial_cash) - 1.0 if portfolio.initial_cash else base.total_return,
        win_rate=base.win_rate,
        profit_factor=base.profit_factor,
        expectancy=base.expectancy,
        avg_holding_hours=base.avg_holding_hours,
        best_trade_pct=base.best_trade_pct,
        worst_trade_pct=base.worst_trade_pct,
        initial_cash=portfolio.initial_cash,
        cash=portfolio.cash,
        equity=equity,
        realized_pnl=portfolio.realized_pnl,
        unrealized_pnl=unrealized,
        max_drawdown=max_dd,
        expectancy_eur=base.expectancy_eur,
        valuation_mode=portfolio.valuation_mode,
    )
