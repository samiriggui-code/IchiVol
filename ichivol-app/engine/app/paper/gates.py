"""Optional entry gates for experimental paper profiles. Every gate is OFF unless its profile key is set,
so the running baseline behaves exactly as before. Returns the FIRST failing reason (exclusive) or None.

Profile keys: one_position_per_symbol, max_symbol_notional_pct, max_open_risk_pct, daily_loss_limit_pct,
one_entry_per_signal_run, reentry_cooldown_hours (no re-entry on a symbol just stopped), correlation_groups (lots that
are one same bet). ``no_atr_stop`` and ``max_positions`` are reported for every gated profile.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import PaperEquitySnapshot, PaperPortfolio, PaperPosition

GATE_KEYS = (
    "one_position_per_symbol", "max_symbol_notional_pct", "max_open_risk_pct", "daily_loss_limit_pct",
    "one_entry_per_signal_run", "reentry_cooldown_hours", "correlation_groups",
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


STOP_EXIT_REASONS = ("stop_hit", "stop_gap")


def recent_stop_ages(session: Session, portfolio: PaperPortfolio, now: datetime | None = None) -> dict[str, float]:
    """Symbole -> secondes depuis son dernier stop, sur la fenêtre ``reentry_cooldown_hours`` du profil (vide sans
    cette clé). Pour ``risk_kernel.PortfolioState.recent_stop_ages``."""
    hours = float((portfolio.strategy_profile or {}).get("reentry_cooldown_hours") or 0.0)
    if hours <= 0:
        return {}
    now = now or datetime.now(timezone.utc)
    rows = session.execute(
        select(PaperPosition.symbol, func.max(PaperPosition.exit_time)).where(
            PaperPosition.portfolio_id == portfolio.id,
            PaperPosition.status == "CLOSED",
            PaperPosition.exit_reason.in_(STOP_EXIT_REASONS),
            PaperPosition.exit_time > now - timedelta(hours=hours),
        ).group_by(PaperPosition.symbol)
    ).all()
    return {symbol: max(0.0, (now - closed_at).total_seconds()) for symbol, closed_at in rows}


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
        recent_stop_ages=recent_stop_ages(session, portfolio, now),
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
