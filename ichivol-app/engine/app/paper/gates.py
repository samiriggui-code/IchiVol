"""Optional entry gates for experimental paper profiles. Every gate is OFF unless its profile key is set,
so the running baseline behaves exactly as before. Returns the FIRST failing reason (exclusive) or None.

Profile keys: one_position_per_symbol, max_symbol_notional_pct, max_open_risk_pct, daily_loss_limit_pct,
one_entry_per_signal_run. ``no_atr_stop`` and ``max_positions`` are reported for every gated profile.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import PaperEquitySnapshot, PaperPortfolio, PaperPosition

GATE_KEYS = (
    "one_position_per_symbol", "max_symbol_notional_pct", "max_open_risk_pct", "daily_loss_limit_pct",
    "one_entry_per_signal_run",
)

# (portfolio_id, symbol, timeframe) -> run id of the last signal run already traded. In-memory and best effort:
# lost on restart (the research simulator is the reference implementation of this rule).
_TRADED_RUN: dict[tuple[str, str, str], int] = {}
_RUN: dict[tuple[str, str, str], tuple[str, int]] = {}


def reset_run_memory() -> None:
    _TRADED_RUN.clear()
    _RUN.clear()


def has_gates(profile: dict[str, Any] | None) -> bool:
    return any((profile or {}).get(k) for k in GATE_KEYS)


def observe_decision(portfolio_id: str, symbol: str, timeframe: str, decision: str) -> int:
    """Call once per cycle with the decision used for this portfolio; returns the current signal-run id."""
    key = (portfolio_id, symbol, timeframe)
    prev = _RUN.get(key)
    if prev is None or prev[0] != decision:
        _RUN[key] = (decision, (prev[1] + 1) if prev else 1)
    return _RUN[key][1]


def traded_run_id(portfolio_id: str, symbol: str, timeframe: str) -> int | None:
    return _TRADED_RUN.get((portfolio_id, symbol, timeframe))


def mark_run_traded(portfolio_id: str, symbol: str, timeframe: str, run_id: int) -> None:
    _TRADED_RUN[(portfolio_id, symbol, timeframe)] = run_id


def open_positions(session: Session, portfolio_id: str) -> list[PaperPosition]:
    return list(session.execute(
        select(PaperPosition).where(PaperPosition.portfolio_id == portfolio_id, PaperPosition.status == "OPEN")
    ).scalars())


def day_start_equity(session: Session, portfolio: PaperPortfolio, now: datetime | None = None) -> float:
    now = now or datetime.now(timezone.utc)
    midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
    row = session.execute(
        select(PaperEquitySnapshot.equity).where(
            PaperEquitySnapshot.portfolio_id == portfolio.id, PaperEquitySnapshot.timestamp < midnight
        ).order_by(PaperEquitySnapshot.timestamp.desc()).limit(1)
    ).scalar_one_or_none()
    return float(row) if row is not None else float(portfolio.initial_cash)


def entry_gate(
    session: Session, portfolio: PaperPortfolio, *, symbol: str, timeframe: str, price: float,
    stop_distance: float | None, equity: float, run_id: int | None = None, now: datetime | None = None,
) -> str | None:
    """Session adapter — delegates pure checks to ``risk_kernel.evaluate_entry_codes`` (T13b)."""
    from app.paper.risk_kernel import OpenPlan, PortfolioState, evaluate_entry_codes, open_lots_from_positions

    p: dict[str, Any] = portfolio.strategy_profile or {}
    opens = open_positions(session, portfolio.id)
    traded = None
    if run_id is not None:
        traded = _TRADED_RUN.get((portfolio.id, symbol, timeframe))
    state = PortfolioState(
        cash=float(portfolio.cash),
        equity=float(equity),
        profile=p,
        open_positions=open_lots_from_positions(opens),
        day_start_equity=day_start_equity(session, portfolio, now),
        traded_run_id=traded,
    )
    plan = OpenPlan(
        symbol=symbol,
        timeframe=timeframe,
        direction="LONG",  # unused by evaluate_entry_codes
        price=price,
        stop_distance=stop_distance,
        run_id=run_id,
    )
    return evaluate_entry_codes(plan, state)
