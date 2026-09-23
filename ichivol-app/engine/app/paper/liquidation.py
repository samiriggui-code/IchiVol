"""Liquidation preview — what cash would become if every open lot closed now.

Uses the same friction / commission path as ``close_capital_position`` without
writing anything. Mid-mark equity is optimistic vs this value whenever fees apply.
"""

from __future__ import annotations

from typing import Any

from app.db.models import PaperPortfolio, PaperPosition
from app.paper.broker import _commission, _friction, _profile
from app.paper.risk import apply_exit_friction
from app.paper.strategy_profiles import BASELINE_PROFILE


def preview_close_cash_delta(
    position: PaperPosition,
    *,
    mark_price: float,
    profile: dict[str, Any] | None = None,
) -> dict[str, float]:
    """Simulate a market close at ``mark_price`` (candle-friction path).

    Returns exit_fill, exit_fee, cash_delta (change to portfolio.cash), realized.
    """
    if not position.qty or position.qty <= 0:
        return {"exit_fill": mark_price, "exit_fee": 0.0, "cash_delta": 0.0, "realized": 0.0}
    prof = profile if profile is not None else dict(BASELINE_PROFILE)
    spread_bps, slip_bps = _friction(prof, position.symbol)
    exit_fill = apply_exit_friction(
        mark_price,
        direction=position.direction,
        spread_bps=spread_bps,
        slippage_bps=slip_bps,
    )
    exit_fee = _commission(prof, position.qty * exit_fill, position.qty, position.symbol)
    entry_notional = float(position.notional or 0.0)
    entry_fee = float(position.entry_fee or 0.0)
    if position.direction == "LONG":
        proceeds = position.qty * exit_fill
        realized = proceeds - exit_fee - entry_notional - entry_fee
        cash_delta = proceeds - exit_fee
    else:
        pnl_pct = (position.entry_price / exit_fill) - 1.0
        realized = entry_notional * pnl_pct - exit_fee
        cash_delta = entry_notional + realized
    return {
        "exit_fill": float(exit_fill),
        "exit_fee": float(exit_fee),
        "cash_delta": float(cash_delta),
        "realized": float(realized),
    }


def liquidation_value(
    portfolio: PaperPortfolio,
    opens: list[PaperPosition],
    marks: dict[str, float],
) -> tuple[float, list[str]]:
    """Cash after closing every open lot at current marks (friction applied).

    Returns (liquidation_value, symbols_without_mark).
    """
    profile = _profile(portfolio)
    cash = float(portfolio.cash)
    missing: list[str] = []
    for p in opens:
        if p.status != "OPEN" or not p.qty:
            continue
        px = marks.get(p.symbol.upper()) or marks.get(p.symbol)
        if px is None:
            missing.append(p.symbol)
            continue
        sim = preview_close_cash_delta(p, mark_price=float(px), profile=profile)
        cash += sim["cash_delta"]
    return cash, missing
