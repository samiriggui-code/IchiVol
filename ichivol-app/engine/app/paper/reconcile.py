"""Read-only fidelity checks for a paper portfolio (T0-BROKER).

Does not mutate cash, positions, or the ledger. Each check returns
``{name, ok, expected, actual, delta, positions}``.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.brokerage import persistence as ledger_db
from app.brokerage.ledger import Cause
from app.db.models import LedgerLeg, LedgerTransaction, PaperOrder, PaperPortfolio, PaperPosition
from app.paper.liquidation import liquidation_value
from app.paper.marks import resolve_marks

_TOL = Decimal("0.0001")
_FTOL = 1e-4


def _check(
    name: str,
    *,
    ok: bool,
    expected: Any,
    actual: Any,
    delta: Any = None,
    positions: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "name": name,
        "ok": bool(ok),
        "expected": expected,
        "actual": actual,
        "delta": delta,
        "positions": positions or [],
    }


def reconcile_portfolio(session: Session, portfolio: PaperPortfolio) -> dict[str, Any]:
    """Run all fidelity checks against live DB rows for ``portfolio``."""
    positions = list(
        session.execute(
            select(PaperPosition).where(PaperPosition.portfolio_id == portfolio.id)
        ).scalars()
    )
    orders = list(
        session.execute(
            select(PaperOrder).where(
                PaperOrder.portfolio_id == portfolio.id, PaperOrder.status == "FILLED"
            )
        ).scalars()
    )
    opens = [p for p in positions if p.status in ("OPEN", "CLOSING")]
    closed = [p for p in positions if p.status == "CLOSED"]
    all_orders = list(
        session.execute(
            select(PaperOrder).where(PaperOrder.portfolio_id == portfolio.id)
        ).scalars()
    )

    checks: list[dict[str, Any]] = []

    cash_gap = ledger_db.reconcile_cash(session, portfolio)
    checks.append(
        _check(
            "cash_vs_ledger",
            ok=abs(cash_gap) <= _TOL,
            expected=float(portfolio.cash),
            actual=float(
                ledger_db.balances(session, portfolio.id).get(portfolio.currency, Decimal(0))
            ),
            delta=float(cash_gap),
        )
    )

    reconstructed = _reconstruct_cash_from_orders(session, portfolio, orders, positions)
    gap = float(portfolio.cash) - reconstructed
    checks.append(
        _check(
            "cash_vs_orders_and_financing",
            ok=abs(gap) <= max(_FTOL, abs(float(portfolio.cash)) * 1e-6 + 0.01),
            expected=reconstructed,
            actual=float(portfolio.cash),
            delta=gap,
        )
    )

    sum_closed = sum(float(p.realized_pnl or 0.0) for p in closed)
    rpnl = float(portfolio.realized_pnl or 0.0)
    checks.append(
        _check(
            "realized_pnl_vs_closed_positions",
            ok=abs(rpnl - sum_closed) <= max(_FTOL, abs(rpnl) * 1e-6 + 0.01),
            expected=sum_closed,
            actual=rpnl,
            delta=rpnl - sum_closed,
        )
    )

    bad_closed: list[str] = []
    for p in closed:
        pos_orders = [o for o in orders if o.position_id == p.id]
        open_side = "BUY" if p.direction == "LONG" else "SELL"
        close_side = "SELL" if p.direction == "LONG" else "BUY"
        opens_o = [o for o in pos_orders if o.side == open_side]
        closes_o = [o for o in pos_orders if o.side == close_side]
        if len(opens_o) != 1 or len(closes_o) != 1:
            bad_closed.append(p.id)
            continue
        o0, o1 = opens_o[0], closes_o[0]
        if p.qty and abs(float(o0.qty or 0) - float(p.qty)) > _FTOL:
            bad_closed.append(p.id)
            continue
        if abs(float(o0.filled_price or 0) - float(p.entry_price)) > max(
            _FTOL, abs(float(p.entry_price)) * 1e-5
        ):
            bad_closed.append(p.id)
            continue
        if p.exit_price is not None and abs(float(o1.filled_price or 0) - float(p.exit_price)) > max(
            _FTOL, abs(float(p.exit_price)) * 1e-5
        ):
            bad_closed.append(p.id)
    checks.append(
        _check(
            "closed_positions_have_open_and_close_orders",
            ok=not bad_closed,
            expected="1 open FILLED + 1 close FILLED matching entry/exit",
            actual=f"{len(bad_closed)} mismatched",
            delta=len(bad_closed),
            positions=bad_closed,
        )
    )

    bad_open: list[str] = []
    for p in opens:
        pos_orders = [o for o in orders if o.position_id == p.id]
        open_side = "BUY" if p.direction == "LONG" else "SELL"
        if not any(o.side == open_side for o in pos_orders):
            bad_open.append(p.id)
    checks.append(
        _check(
            "open_positions_have_entry_order",
            ok=not bad_open,
            expected="≥1 entry FILLED order",
            actual=f"{len(bad_open)} missing",
            delta=len(bad_open),
            positions=bad_open,
        )
    )

    syms = {p.symbol for p in opens}
    marks = resolve_marks(syms, timeframe="1h", allow_fetch=True)
    mark_px = {s: m.price for s, m in marks.items() if m.source != "missing"}
    invested = sum(float(p.notional or 0.0) for p in opens)
    unrealized = 0.0
    unpriced: list[str] = []
    for p in opens:
        m = marks.get(p.symbol.upper())
        if m is None or m.source == "missing" or not p.qty:
            unpriced.append(p.symbol)
            continue
        if p.direction == "LONG":
            unrealized += float(p.qty) * (m.price - float(p.entry_price))
        else:
            unrealized += float(p.qty) * (float(p.entry_price) - m.price)
    equity = float(portfolio.cash) + invested + unrealized
    checks.append(
        _check(
            "equity_identity",
            ok=True,
            expected=float(portfolio.cash) + invested + unrealized,
            actual=equity,
            delta=0.0,
        )
    )
    checks.append(
        _check(
            "no_open_without_mark",
            ok=not unpriced,
            expected="all OPEN lots priced",
            actual=f"{len(unpriced)} unpriced",
            delta=len(unpriced),
            positions=unpriced,
        )
    )

    liq, liq_missing = liquidation_value(portfolio, opens, mark_px)
    fee_gap = equity - liq
    checks.append(
        _check(
            "liquidation_value_vs_equity",
            ok=(not opens) or fee_gap >= -_FTOL,
            expected="liquidation_value ≤ mid equity when exit friction applies",
            actual=liq,
            delta=fee_gap,
            positions=liq_missing,
        )
    )

    legacy = _short_pnl_legacy_check(closed)
    checks.append(legacy)

    # —— T13d order lifecycle checks (report only; no cash mutation) ——
    checks.extend(_order_lifecycle_checks(session, portfolio, positions, all_orders))

    anomalies = [c for c in checks if not c["ok"]]
    return {
        "portfolio_code": portfolio.code,
        "ok": len(anomalies) == 0,
        "anomaly_count": len(anomalies),
        "checks": checks,
        "equity": equity,
        "liquidation_value": liq,
        "cash": float(portfolio.cash),
        "short_pnl_legacy": {
            "positions": legacy.get("positions") or [],
            "delta_total": legacy.get("delta"),
            "details": legacy.get("expected"),
        },
    }


def _ledger_keys(session: Session, portfolio_id: str) -> set[str]:
    return set(
        session.execute(
            select(LedgerTransaction.key).where(LedgerTransaction.portfolio_id == portfolio_id)
        ).scalars().all()
    )


def _order_lifecycle_checks(
    session: Session,
    portfolio: PaperPortfolio,
    positions: list[PaperPosition],
    all_orders: list[PaperOrder],
) -> list[dict[str, Any]]:
    """T13d divergence report — never mutates cash / positions."""
    from app.paper import orders as paper_orders

    checks: list[dict[str, Any]] = []
    filled = [o for o in all_orders if o.status == paper_orders.FILLED]
    keys = _ledger_keys(session, portfolio.id)
    opens = [p for p in positions if p.status in ("OPEN", "CLOSING")]
    closed = [p for p in positions if p.status == "CLOSED"]

    missing_entry: list[str] = []
    for p in opens:
        open_side = "BUY" if p.direction == "LONG" else "SELL"
        if not any(
            o.position_id == p.id and o.side == open_side and o.status == paper_orders.FILLED
            for o in filled
        ):
            missing_entry.append(p.id)
    checks.append(
        _check(
            "open_has_entry_filled_order",
            ok=not missing_entry,
            expected="OPEN/CLOSING → ≥1 entry FILLED",
            actual=f"{len(missing_entry)} missing",
            delta=len(missing_entry),
            positions=missing_entry,
        )
    )

    qty_mismatch: list[str] = []
    for p in opens:
        if not p.qty:
            continue
        pos_o = [o for o in filled if o.position_id == p.id]
        open_side = "BUY" if p.direction == "LONG" else "SELL"
        close_side = "SELL" if p.direction == "LONG" else "BUY"
        entry_qty = sum(float(o.filled_qty or o.qty or 0) for o in pos_o if o.side == open_side)
        exit_qty = sum(float(o.filled_qty or o.qty or 0) for o in pos_o if o.side == close_side)
        net = entry_qty - exit_qty
        if abs(net - float(p.qty)) > max(_FTOL, abs(float(p.qty)) * 1e-6):
            qty_mismatch.append(p.id)
    checks.append(
        _check(
            "filled_qty_matches_open_position",
            ok=not qty_mismatch,
            expected="Σ entry − exit filled_qty = position.qty",
            actual=f"{len(qty_mismatch)} mismatched",
            delta=len(qty_mismatch),
            positions=qty_mismatch,
        )
    )

    missing_ledger: list[str] = []
    for o in filled:
        reason = (o.reason or "").lower()
        candidates: list[str] = []
        if reason == "open" and o.position_id:
            candidates = [f"open:{o.position_id}"]
        elif o.position_id and reason in ("partial_tp", "partial"):
            candidates = [f"partial:{o.position_id}:{s}" for s in range(1, 32)]
        elif o.position_id and reason == "reinforce":
            candidates = [f"reinforce:{o.position_id}:{s}" for s in range(1, 32)]
        elif o.position_id:
            candidates = [f"close:{o.position_id}"]
        if candidates and not any(c in keys for c in candidates):
            # also accept client_order_id as ledger key for partial/reinforce
            if o.client_order_id and o.client_order_id in keys:
                continue
            missing_ledger.append(o.id)
    checks.append(
        _check(
            "filled_order_has_ledger",
            ok=not missing_ledger,
            expected="FILLED order → ledger key",
            actual=f"{len(missing_ledger)} missing",
            delta=len(missing_ledger),
            positions=missing_ledger,
        )
    )

    missing_close: list[str] = []
    for p in closed:
        close_side = "SELL" if p.direction == "LONG" else "BUY"
        if not any(
            o.position_id == p.id and o.side == close_side and o.status == paper_orders.FILLED
            for o in filled
        ):
            missing_close.append(p.id)
    checks.append(
        _check(
            "closed_has_close_filled_order",
            ok=not missing_close,
            expected="CLOSED → close FILLED order",
            actual=f"{len(missing_close)} missing",
            delta=len(missing_close),
            positions=missing_close,
        )
    )

    stale = [
        o.id
        for o in all_orders
        if o.status not in paper_orders.TERMINAL
        and o.created_at is not None
        and (datetime.now(timezone.utc) - o.created_at).total_seconds() > 30 * 60
    ]
    checks.append(
        _check(
            "no_stale_non_terminal_orders",
            ok=not stale,
            expected="no non-terminal order older than 30 min",
            actual=f"{len(stale)} stale",
            delta=len(stale),
            positions=stale,
        )
    )
    return checks


def apply_stale_order_reconciliation(
    session: Session,
    portfolio: PaperPortfolio,
    *,
    stale_minutes: float = 30.0,
) -> dict[str, Any]:
    """Mutate order statuses only: stale → UNKNOWN → FILLED|CANCELLED via ledger.

    Never touches cash, positions, or ledger rows.
    """
    from app.paper import orders as paper_orders

    keys = _ledger_keys(session, portfolio.id)
    now = datetime.now(timezone.utc)
    cutoff = stale_minutes * 60.0
    rows = list(
        session.execute(
            select(PaperOrder).where(PaperOrder.portfolio_id == portfolio.id)
        ).scalars()
    )
    marked: list[str] = []
    resolved: list[dict[str, str]] = []
    for o in rows:
        if o.status in paper_orders.TERMINAL:
            continue
        age = (now - (o.created_at or now)).total_seconds()
        if o.status != paper_orders.UNKNOWN and age > cutoff:
            paper_orders.mark_unknown(session, o, reason="stale_reconcile", at=now)
            marked.append(o.id)
        if o.status != paper_orders.UNKNOWN:
            continue
        # Resolve via ledger presence
        coid = o.client_order_id or ""
        pos = o.position_id
        has_fill = False
        if coid and coid in keys:
            has_fill = True
        if pos and f"open:{pos}" in keys and (o.reason or "") == "open":
            has_fill = True
        if pos and f"close:{pos}" in keys and (o.reason or "") not in ("open", "reinforce", "partial_tp"):
            has_fill = True
        if has_fill:
            paper_orders.resolve_unknown(session, o, to=paper_orders.FILLED, reason="ledger_present", at=now)
            resolved.append({"id": o.id, "to": paper_orders.FILLED})
        else:
            paper_orders.resolve_unknown(session, o, to=paper_orders.CANCELLED, reason="ledger_absent", at=now)
            resolved.append({"id": o.id, "to": paper_orders.CANCELLED})
    return {"marked_unknown": marked, "resolved": resolved}



def _short_pnl_legacy_check(closed: list[PaperPosition]) -> dict[str, Any]:
    """Read-only: CLOSED SHORT lots closed before the formula fix, with stored − correct Δ."""
    from app.paper.broker import short_pnl_pct, short_realized_currency

    details: list[dict[str, Any]] = []
    total_delta = 0.0
    ids: list[str] = []
    for p in closed:
        if p.direction != "SHORT" or p.exit_price is None or not p.entry_price:
            continue
        exit_t = p.exit_time
        if exit_t is None:
            continue
        day = exit_t.date() if exit_t.tzinfo else exit_t.replace(tzinfo=timezone.utc).date()
        if day >= SHORT_PNL_FIX_ACTIVATED_ON:
            continue
        correct_pct = short_pnl_pct(float(p.entry_price), float(p.exit_price))
        correct_ccy = (
            short_realized_currency(float(p.qty), float(p.entry_price), float(p.exit_price))
            if p.qty
            else None
        )
        stored_pct = float(p.pnl_pct) if p.pnl_pct is not None else None
        stored_rpnl = float(p.realized_pnl) if p.realized_pnl is not None else None
        # Compare currency PnL excluding fees when we can reconstruct from prices;
        # report pct delta as primary signal of the reciprocal bug.
        delta_pct = (stored_pct - correct_pct) if stored_pct is not None else None
        delta_ccy = None
        if stored_rpnl is not None and correct_ccy is not None:
            # Stored realized includes fees/financing; compare gross price PnL only via pct.
            delta_ccy = (
                float(p.qty) * float(p.entry_price) * (stored_pct - correct_pct)
                if p.qty and stored_pct is not None
                else None
            )
        if delta_pct is None or abs(delta_pct) <= _FTOL:
            continue
        ids.append(p.id)
        total_delta += float(delta_ccy or 0.0)
        details.append(
            {
                "position_id": p.id,
                "symbol": p.symbol,
                "entry": float(p.entry_price),
                "exit": float(p.exit_price),
                "stored_pnl_pct": stored_pct,
                "correct_pnl_pct": correct_pct,
                "delta_pct": delta_pct,
                "delta_currency_est": delta_ccy,
                "exit_day": day.isoformat(),
            }
        )
    return _check(
        "short_pnl_legacy_formula",
        # Informational: never rewrite history; do not fail the portfolio badge.
        ok=True,
        expected=details,
        actual=f"{len(details)} CLOSED SHORT(s) pre-fix (stored − correct)",
        delta=total_delta,
        positions=ids,
    )


def _reconstruct_cash_from_orders(
    session: Session,
    portfolio: PaperPortfolio,
    orders: list[PaperOrder],
    positions: list[PaperPosition],
) -> float:
    """initial − Σ open (notional+fee) + Σ close cash_delta + Σ FINANCING."""
    from app.paper.broker import short_realized_currency

    cash = float(portfolio.initial_cash)
    by_id = {p.id: p for p in positions}
    for o in sorted(orders, key=lambda x: x.created_at or datetime(1970, 1, 1, tzinfo=timezone.utc)):
        notional = float(o.notional or 0.0)
        fee = float(o.fee or 0.0)
        pos = by_id.get(o.position_id) if o.position_id else None
        if (o.reason or "") == "open":
            cash -= notional + fee
            continue
        # Close order
        if pos is not None and pos.direction == "SHORT" and pos.entry_price and o.filled_price:
            entry_notional = float(pos.notional or 0.0)
            exit_fill = float(o.filled_price)
            pnl = short_realized_currency(float(pos.qty or 0.0), float(pos.entry_price), exit_fill)
            cash += entry_notional + pnl - fee
        else:
            cash += notional - fee

    fin_legs = session.execute(
        select(LedgerLeg.amount)
        .join(LedgerTransaction, LedgerLeg.transaction_id == LedgerTransaction.id)
        .where(
            LedgerTransaction.portfolio_id == portfolio.id,
            LedgerLeg.cause == Cause.FINANCING.value,
        )
    ).scalars().all()
    for amt in fin_legs:
        cash += float(amt)
    return cash
