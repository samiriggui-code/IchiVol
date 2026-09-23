"""Paper trading positions, portfolios, preview, propose."""

from __future__ import annotations

import time

from fastapi import APIRouter, HTTPException

from app.api.common import (
    _atr_params_override,
    _latest_marks,
    _paper_perf_dict,
    _paper_position_dict,
    _portfolio_dict,
    _rvol_params_override,
)
from app.config import settings
from app.db.models import PaperPartialExit
from app.db.session import SessionLocal
from app.paper import engine as paper_engine
from sqlalchemy import select
from app.paper.costs import compute_costs
from app.paper.performance import compute_performance, compute_portfolio_performance
from app.paper.portfolio import (
    ensure_baseline_portfolio,
    ensure_portfolio,
    ensure_syncable_portfolios,
    get_portfolio_by_code,
    list_portfolios,
)
from app.paper.strategy_profiles import ALL_PROFILES, BASELINE_CODE
from app.paper.verdict import compute_progress


def _partials_by_position(session, position_ids: list[str]) -> dict[str, list]:
    if not position_ids:
        return {}
    rows = session.execute(
        select(PaperPartialExit)
        .where(PaperPartialExit.position_id.in_(position_ids))
        .order_by(PaperPartialExit.position_id, PaperPartialExit.seq)
    ).scalars()
    out: dict[str, list] = {}
    for e in rows:
        out.setdefault(e.position_id, []).append(e)
    return out
from app.screener.cache import screener_cache
from app.screener.service import scan_symbol

router_before_shadow = APIRouter(prefix=settings.engine_api_prefix, tags=["engine"])

@router_before_shadow.get("/paper/positions")
def list_paper_positions(
    source: str | None = None, user_id: str | None = None, status: str | None = None
) -> dict:
    """Virtual positions only (CDC V2 "Paper trading") -- app/paper/engine.py
    owns open/close rules, this just lists them. `source=auto_watchlist`
    (no `user_id`) is the background screener's own shadow portfolio;
    `source=user_confirmed` + `user_id` is one user's confirmed picks."""
    session = SessionLocal()
    try:
        positions = paper_engine.list_positions(session, source=source, user_id=user_id, status=status)
        by = _partials_by_position(session, [p.id for p in positions])
        return {
            "positions": [
                _paper_position_dict(p, partial_exits=by.get(p.id, [])) for p in positions
            ]
        }
    finally:
        session.close()


@router_before_shadow.get("/paper/performance")
def get_paper_performance(source: str | None = None, user_id: str | None = None) -> dict:
    """Trade-level + capital performance when baseline portfolio exists."""
    session = SessionLocal()
    try:
        positions = paper_engine.list_positions(session, source=source, user_id=user_id)
        portfolio = ensure_baseline_portfolio(session)
        session.commit()
        if source in (None, "auto_watchlist") and user_id is None:
            perf = compute_portfolio_performance(session, portfolio, positions)
        else:
            perf = compute_performance(positions)
        return _paper_perf_dict(perf)
    finally:
        session.close()


@router_before_shadow.get("/paper/portfolios")
def get_paper_portfolios() -> dict:
    session = SessionLocal()
    try:
        ensure_syncable_portfolios(session)
        session.commit()
        return {"portfolios": [_portfolio_dict(p) for p in list_portfolios(session)]}
    finally:
        session.close()


@router_before_shadow.get("/paper/portfolios/{code}/overview")
def get_paper_portfolio_overview(code: str) -> dict:
    """Broker-style account view: cash / invested / unrealized P&L, open positions
    marked to screener cache or last candle, equity + liquidation_value. Read-only.
    """
    from datetime import datetime, timedelta, timezone

    from sqlalchemy import select

    from app.db.models import PaperEquitySnapshot
    from app.paper.liquidation import liquidation_value
    from app.paper.marks import OVERVIEW_FETCH_BUDGET_S, mark_stale, resolve_marks

    session = SessionLocal()
    try:
        portfolio = get_portfolio_by_code(session, code)
        if portfolio is None:
            raise HTTPException(status_code=404, detail="portfolio_not_found")
        positions = paper_engine.list_positions(session, portfolio_id=portfolio.id)
        opens = [p for p in positions if p.status == "OPEN"]
        # Prefer each lot's own timeframe. Never block Synthèse on Twelve Data waits.
        by_tf: dict[str, list[str]] = {}
        for p in opens:
            by_tf.setdefault(p.timeframe or "1h", []).append(p.symbol)
        marks_by_sym: dict = {}
        t0 = time.monotonic()
        for tf, syms in by_tf.items():
            remaining = OVERVIEW_FETCH_BUDGET_S - (time.monotonic() - t0)
            marks_by_sym.update(
                resolve_marks(
                    syms,
                    timeframe=tf,
                    allow_fetch=True,
                    fetch_budget_s=max(0.0, remaining),
                    block_on_provider=False,
                )
            )
        leftover = {p.symbol for p in opens} - {s for s in marks_by_sym}
        if leftover:
            remaining = OVERVIEW_FETCH_BUDGET_S - (time.monotonic() - t0)
            marks_by_sym.update(
                resolve_marks(
                    leftover,
                    timeframe="1h",
                    allow_fetch=True,
                    fetch_budget_s=max(0.0, remaining),
                    block_on_provider=False,
                )
            )

        rows: list[dict] = []
        invested = 0.0
        unrealized = 0.0
        open_entry_fees = 0.0
        incomplete_open = 0
        stale_open = 0
        mark_px: dict[str, float] = {}
        by_partial = _partials_by_position(session, [p.id for p in positions])
        for p in positions:
            d = _paper_position_dict(p, partial_exits=by_partial.get(p.id, []))
            d["current_price"] = None
            d["unrealized_pnl"] = None
            d["unrealized_pct"] = None
            d["market_value"] = None
            d["valuation_status"] = None
            d["mark_source"] = None
            d["mark_age_s"] = None
            d["mark_stale"] = None
            if p.status == "OPEN":
                invested += p.notional or 0.0
                open_entry_fees += float(p.entry_fee or 0.0)
                mark = marks_by_sym.get(p.symbol.upper())
                now_s = time.time()
                if p.qty is None:
                    d["valuation_status"] = "missing_qty"
                    incomplete_open += 1
                elif mark is None or mark.source == "missing":
                    d["valuation_status"] = "missing_mark"
                    incomplete_open += 1
                elif p.notional is None:
                    d["valuation_status"] = "missing_notional"
                    incomplete_open += 1
                else:
                    d["valuation_status"] = "priced"
                    mark_px[p.symbol.upper()] = mark.price
                if mark is not None and mark.source != "missing" and p.entry_price:
                    price = mark.price
                    move = (price - p.entry_price) / p.entry_price
                    d["current_price"] = price
                    d["price_as_of"] = mark.as_of
                    d["mark_source"] = mark.source
                    d["mark_age_s"] = max(0.0, now_s - float(mark.as_of))
                    stale = mark_stale(mark, p.timeframe or "1h", now=now_s)
                    d["mark_stale"] = stale
                    if stale:
                        stale_open += 1
                        if d["valuation_status"] == "priced":
                            d["valuation_status"] = "stale_mark"
                    d["unrealized_pct"] = move if p.direction == "LONG" else -move
                    if p.qty:
                        gain = (
                            p.qty * (price - p.entry_price)
                            if p.direction == "LONG"
                            else p.qty * (p.entry_price - price)
                        )
                        d["unrealized_pnl"] = gain
                        d["market_value"] = p.qty * price
                        unrealized += gain
            rows.append(d)

        equity = portfolio.cash + invested + unrealized
        liq, _missing_liq = liquidation_value(portfolio, opens, mark_px)
        realized = float(portfolio.realized_pnl or 0.0)
        total_pnl = equity - portfolio.initial_cash
        snaps = (
            session.execute(
                select(PaperEquitySnapshot)
                .where(PaperEquitySnapshot.portfolio_id == portfolio.id)
                .order_by(PaperEquitySnapshot.timestamp.desc())
                .limit(500)
            )
            .scalars()
            .all()
        )
        curve = [
            {"t": s.timestamp.isoformat(), "equity": s.equity}
            for s in reversed(snaps)
        ]
        day_ago = datetime.now(timezone.utc) - timedelta(hours=24)
        ref = next(
            (
                s.equity
                for s in snaps
                if (s.timestamp if s.timestamp.tzinfo else s.timestamp.replace(tzinfo=timezone.utc))
                <= day_ago
            ),
            None,
        )
        open_n = sum(1 for r in rows if r["status"] == "OPEN")
        priced_n = sum(
            1 for r in rows if r["status"] == "OPEN" and r["valuation_status"] in ("priced", "stale_mark")
        )
        return {
            "portfolio": _portfolio_dict(portfolio),
            "account": {
                "initial_cash": portfolio.initial_cash,
                "cash": portfolio.cash,
                "invested": invested,
                "unrealized_pnl": unrealized,
                "realized_pnl": realized,
                "equity": equity,
                "liquidation_value": liq,
                "total_pnl": total_pnl,
                "day_change": (equity - ref) if ref is not None else None,
                "open_entry_fees": open_entry_fees,
                "realized_plus_unrealized": realized + unrealized,
                "pnl_explained": realized + unrealized - open_entry_fees,
                "priced_positions": priced_n,
                "incomplete_open": incomplete_open,
                "stale_open": stale_open,
                "open_positions": open_n,
            },
            "positions": rows[:200],
            "equity_curve": curve,
            "costs": compute_costs(session, portfolio, equity=equity),
            "progress": compute_progress(session, portfolio, equity=equity),
        }
    finally:
        session.close()


@router_before_shadow.get("/paper/portfolios/{code}/reconcile")
def get_paper_portfolio_reconcile(code: str) -> dict:
    """Read-only fidelity audit of cash / ledger / orders / marks (T0-BROKER)."""
    from app.paper.reconcile import reconcile_portfolio

    session = SessionLocal()
    try:
        portfolio = get_portfolio_by_code(session, code)
        if portfolio is None:
            raise HTTPException(status_code=404, detail="portfolio_not_found")
        return reconcile_portfolio(session, portfolio)
    finally:
        session.close()


@router_before_shadow.get("/paper/portfolios/{code}/activity")
def get_paper_portfolio_activity(code: str, limit: int = 100) -> dict:
    """Virtual fill log (buys / sells) newest first, for the broker-style activity
    journal. Read-only; never a real venue.
    """
    from sqlalchemy import select

    from app.db.models import PaperOrder

    session = SessionLocal()
    try:
        portfolio = get_portfolio_by_code(session, code)
        if portfolio is None:
            raise HTTPException(status_code=404, detail="portfolio_not_found")
        orders = (
            session.execute(
                select(PaperOrder)
                .where(PaperOrder.portfolio_id == portfolio.id)
                .order_by(PaperOrder.created_at.desc())
                .limit(max(1, min(limit, 500)))
            )
            .scalars()
            .all()
        )
        return {
            "orders": [
                {
                    "id": o.id,
                    "position_id": o.position_id,
                    "time": o.created_at.isoformat(),
                    "symbol": o.symbol,
                    "timeframe": o.timeframe,
                    "side": o.side,
                    "requested_price": o.requested_price,
                    "filled_price": o.filled_price,
                    "qty": o.qty,
                    "notional": o.notional,
                    "fee": o.fee,
                    "status": o.status,
                    "reason": o.reason,
                }
                for o in orders
            ]
        }
    finally:
        session.close()


@router_before_shadow.get("/paper/portfolios/{code}")
def get_paper_portfolio(code: str) -> dict:
    session = SessionLocal()
    try:
        if code in ALL_PROFILES:
            ensure_portfolio(session, code)
            session.commit()
        portfolio = get_portfolio_by_code(session, code)
        if portfolio is None:
            raise HTTPException(status_code=404, detail="portfolio_not_found")
        positions = paper_engine.list_positions(session, portfolio_id=portfolio.id)
        perf = compute_portfolio_performance(session, portfolio, positions)
        return {
            "portfolio": _portfolio_dict(portfolio),
            "performance": _paper_perf_dict(perf),
            "positions": [_paper_position_dict(p) for p in positions[:100]],
        }
    finally:
        session.close()


