"""Paper order intents — propose before act (never live).

Builds a sized virtual order from the same risk rules as PaperBroker
(`size_position`) so the UI can show qty / stop / TP before the user
confirms. Opening still goes through `open_user_confirmed`.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from sqlalchemy.orm import Session

from app.paper import broker as paper_broker
from app.paper.portfolio import ensure_baseline_portfolio, get_portfolio_by_code
from app.paper.risk import size_position
from app.paper.strategy_profiles import BASELINE_PROFILE
from app.screener.service import ScreenerRow


@dataclass(frozen=True)
class OrderIntent:
    """Suggested paper trade — not an order until confirmed."""

    actionable: bool
    reason: str
    symbol: str
    timeframe: str
    pipeline_decision: str
    direction: str | None
    price: float
    stop_distance: float | None
    qty: float | None
    notional: float | None
    entry_fill: float | None
    stop_price: float | None
    take_profit_price: float | None
    risk_pct: float | None
    risk_amount: float | None
    portfolio_code: str
    equity: float | None
    cash: float | None
    volume_type: str | None = None
    evidence_summary: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _direction_for(decision: str) -> str | None:
    if decision == "BUY":
        return "LONG"
    if decision == "SELL":
        return "SHORT"
    return None


def _evidence_summary(row: ScreenerRow) -> dict[str, Any] | None:
    if row.evidence is None:
        return None
    h = row.evidence.historical
    return {
        "sample_size": h.sample_size,
        "sample_quality": h.sample_quality.value,
        "status": h.status,
        "calibration_note": row.evidence.calibration_note(),
    }


def propose_order_intent(
    session: Session,
    row: ScreenerRow,
    *,
    portfolio_code: str = "ICHIVOL_BASELINE_V1",
) -> OrderIntent:
    """Dry-run sizing against the baseline (or named) paper portfolio."""
    direction = _direction_for(row.pipeline.decision)
    stop = row.atr.suggested_stop_distance if row.atr is not None else None
    volume_type = row.candles[-1].volume_type.value if row.candles else None
    evidence_summary = _evidence_summary(row)

    def _blocked(reason: str, **extra: Any) -> OrderIntent:
        return OrderIntent(
            actionable=False,
            reason=reason,
            symbol=row.symbol,
            timeframe=row.timeframe,
            pipeline_decision=row.pipeline.decision,
            direction=direction,
            price=row.price,
            stop_distance=stop,
            qty=None,
            notional=None,
            entry_fill=None,
            stop_price=None,
            take_profit_price=None,
            risk_pct=extra.get("risk_pct"),
            risk_amount=None,
            portfolio_code=portfolio_code,
            equity=extra.get("equity"),
            cash=extra.get("cash"),
            volume_type=volume_type,
            evidence_summary=evidence_summary,
        )

    if direction is None:
        return _blocked("not_actionable")
    if stop is None or stop <= 0:
        return _blocked("no_stop")

    portfolio = ensure_baseline_portfolio(session)
    if portfolio_code != portfolio.code:
        alt = get_portfolio_by_code(session, portfolio_code)
        if alt is not None:
            portfolio = alt
            portfolio_code = portfolio.code

    profile = portfolio.strategy_profile or dict(BASELINE_PROFILE)
    equity = paper_broker.estimate_equity(session, portfolio)
    risk_pct = float(profile.get("risk_pct", 0.01))
    sized = size_position(
        equity=equity,
        cash=portfolio.cash,
        direction=direction,
        entry_price=row.price,
        stop_distance=stop,
        risk_pct=risk_pct,
        take_profit_r=float(profile.get("take_profit_r", 2.0)),
        max_notional_pct=float(profile.get("max_notional_pct", 0.25)),
        commission_bps=float(profile.get("commission_bps", 5.0)),
        spread_bps=float(profile.get("spread_bps", 2.0)),
        slippage_bps=float(profile.get("slippage_bps", 3.0)),
    )
    if sized is None:
        return _blocked(
            "insufficient_cash_or_risk",
            risk_pct=risk_pct,
            equity=equity,
            cash=portfolio.cash,
        )

    return OrderIntent(
        actionable=True,
        reason="ok",
        symbol=row.symbol,
        timeframe=row.timeframe,
        pipeline_decision=row.pipeline.decision,
        direction=direction,
        price=row.price,
        stop_distance=stop,
        qty=sized.qty,
        notional=sized.notional,
        entry_fill=sized.entry_fill,
        stop_price=sized.stop_price,
        take_profit_price=sized.take_profit_price,
        risk_pct=sized.risk_pct,
        risk_amount=sized.risk_amount,
        portfolio_code=portfolio_code,
        equity=equity,
        cash=portfolio.cash,
        volume_type=volume_type,
        evidence_summary=evidence_summary,
    )
