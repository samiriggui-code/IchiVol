"""ShadowBroker — counterfactual trades outside portfolio cash.

When Structure / Fib / Context blocks a raw BUY/SELL, open a SHADOW_* trade
with the same SL/TP geometry as Paper. Mark to market; never debit cash.
After N closed shadows: if mean pnl_r > 0 the filter was too aggressive.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import PaperJournalEvent, PaperPortfolio, ShadowPosition
from app.paper.risk import apply_entry_friction, apply_exit_friction
from app.paper.strategy_profiles import BASELINE_PROFILE


def _profile(portfolio: PaperPortfolio) -> dict[str, Any]:
    return portfolio.strategy_profile or dict(BASELINE_PROFILE)


def _direction_for(raw_decision: str) -> str | None:
    if raw_decision == "BUY":
        return "LONG"
    if raw_decision == "SELL":
        return "SHORT"
    return None


def open_shadow(
    session: Session,
    *,
    portfolio: PaperPortfolio,
    symbol: str,
    timeframe: str,
    raw_decision: str,
    price: float,
    stop_distance: float | None,
    block_source: str,
    block_reason: str | None,
    meta: dict[str, Any] | None = None,
) -> ShadowPosition | None:
    """Open a counterfactual position. No cash impact."""
    direction = _direction_for(raw_decision)
    if direction is None or price <= 0:
        return None

    profile = _profile(portfolio)
    stop_dist = float(stop_distance or 0.0)
    if stop_dist <= 0:
        stop_dist = price * 0.01
    risk_pct = float(profile.get("risk_pct", 0.01))
    tp_r = float(profile.get("take_profit_r", 2.0))
    spread = float(profile.get("spread_bps", 2.0))
    slip = float(profile.get("slippage_bps", 3.0))

    # Dedup: one OPEN shadow per portfolio/symbol/tf
    existing = session.execute(
        select(ShadowPosition).where(
            ShadowPosition.portfolio_id == portfolio.id,
            ShadowPosition.symbol == symbol,
            ShadowPosition.timeframe == timeframe,
            ShadowPosition.status == "OPEN",
        )
    ).scalar_one_or_none()
    if existing is not None:
        return existing

    entry = apply_entry_friction(
        price, direction=direction, spread_bps=spread, slippage_bps=slip
    )
    if direction == "LONG":
        stop = entry - stop_dist
        tp = entry + stop_dist * tp_r
    else:
        stop = entry + stop_dist
        tp = entry - stop_dist * tp_r

    now = datetime.now(timezone.utc)
    shadow = ShadowPosition(
        portfolio_id=portfolio.id,
        symbol=symbol,
        timeframe=timeframe,
        direction=direction,
        status="OPEN",
        entry_time=now,
        entry_price=entry,
        stop_price=stop,
        take_profit_price=tp,
        stop_distance=stop_dist,
        risk_pct=risk_pct,
        block_source=block_source,
        block_reason=block_reason,
        raw_decision=raw_decision,
        meta=meta,
        created_at=now,
        updated_at=now,
    )
    session.add(shadow)
    session.flush()

    session.add(
        PaperJournalEvent(
            portfolio_id=portfolio.id,
            position_id=None,
            event_type="SHADOW_OPEN",
            payload={
                "shadow_id": shadow.id,
                "symbol": symbol,
                "timeframe": timeframe,
                "direction": direction,
                "entry_price": entry,
                "stop_price": stop,
                "take_profit_price": tp,
                "block_source": block_source,
                "block_reason": block_reason,
                "raw_decision": raw_decision,
            },
            created_at=now,
        )
    )
    return shadow


def mark_shadows(
    session: Session,
    *,
    marks: dict[str, float],
) -> list[ShadowPosition]:
    """Close shadows that hit SL/TP on mark price. Key = symbol:timeframe."""
    opens = list(
        session.execute(
            select(ShadowPosition).where(ShadowPosition.status == "OPEN")
        ).scalars()
    )
    closed: list[ShadowPosition] = []
    now = datetime.now(timezone.utc)
    for sh in opens:
        key = f"{sh.symbol}:{sh.timeframe}"
        price = marks.get(key)
        if price is None:
            price = marks.get(sh.symbol)
        if price is None or price <= 0:
            continue

        hit: str | None = None
        exit_px = price
        if sh.direction == "LONG":
            if price <= sh.stop_price:
                hit, exit_px = "stop_hit", sh.stop_price
            elif price >= sh.take_profit_price:
                hit, exit_px = "take_profit_hit", sh.take_profit_price
        else:
            if price >= sh.stop_price:
                hit, exit_px = "stop_hit", sh.stop_price
            elif price <= sh.take_profit_price:
                hit, exit_px = "take_profit_hit", sh.take_profit_price

        if hit is None:
            continue

        profile_spread = 2.0
        profile_slip = 3.0
        fill = apply_exit_friction(
            exit_px, direction=sh.direction, spread_bps=profile_spread, slippage_bps=profile_slip
        )
        if sh.direction == "LONG":
            pnl_pct = (fill - sh.entry_price) / sh.entry_price
            pnl_r = (fill - sh.entry_price) / sh.stop_distance if sh.stop_distance else 0.0
        else:
            pnl_pct = (sh.entry_price - fill) / sh.entry_price
            pnl_r = (sh.entry_price - fill) / sh.stop_distance if sh.stop_distance else 0.0

        sh.status = "CLOSED"
        sh.exit_time = now
        sh.exit_price = fill
        sh.exit_reason = hit
        sh.pnl_pct = pnl_pct
        sh.pnl_r = pnl_r
        sh.updated_at = now
        session.add(
            PaperJournalEvent(
                portfolio_id=sh.portfolio_id,
                position_id=None,
                event_type="SHADOW_CLOSE",
                payload={
                    "shadow_id": sh.id,
                    "symbol": sh.symbol,
                    "exit_reason": hit,
                    "exit_price": fill,
                    "pnl_r": pnl_r,
                    "pnl_pct": pnl_pct,
                },
                created_at=now,
            )
        )
        closed.append(sh)
    return closed


def shadow_stats(
    session: Session,
    *,
    portfolio_id: str | None = None,
) -> dict[str, Any]:
    q = select(ShadowPosition)
    if portfolio_id:
        q = q.where(ShadowPosition.portfolio_id == portfolio_id)
    rows = list(session.execute(q).scalars())
    closed = [r for r in rows if r.status == "CLOSED" and r.pnl_r is not None]
    open_n = sum(1 for r in rows if r.status == "OPEN")
    wins = [r for r in closed if (r.pnl_r or 0) > 0]
    losses = [r for r in closed if (r.pnl_r or 0) <= 0]
    mean_r = (
        sum(float(r.pnl_r or 0) for r in closed) / len(closed) if closed else None
    )
    # Positive mean_r ⇒ blocked trades would have won on avg ⇒ filter too aggressive
    filter_verdict = None
    if closed and len(closed) >= 5:
        if mean_r is not None and mean_r > 0.1:
            filter_verdict = "filter_too_aggressive"
        elif mean_r is not None and mean_r < -0.1:
            filter_verdict = "filter_helpful"
        else:
            filter_verdict = "inconclusive"

    by_source: dict[str, dict[str, Any]] = {}
    for r in closed:
        bucket = by_source.setdefault(
            r.block_source,
            {"n": 0, "mean_pnl_r": 0.0, "wins": 0},
        )
        bucket["n"] += 1
        bucket["mean_pnl_r"] += float(r.pnl_r or 0)
        if (r.pnl_r or 0) > 0:
            bucket["wins"] += 1
    for b in by_source.values():
        if b["n"]:
            b["mean_pnl_r"] = b["mean_pnl_r"] / b["n"]
            b["win_rate"] = b["wins"] / b["n"]

    return {
        "n_total": len(rows),
        "n_open": open_n,
        "n_closed": len(closed),
        "n_wins": len(wins),
        "n_losses": len(losses),
        "win_rate": (len(wins) / len(closed)) if closed else None,
        "mean_pnl_r": mean_r,
        "filter_verdict": filter_verdict,
        "by_block_source": by_source,
        "note": (
            "ShadowBroker counterfactuals — hors cash. "
            "mean_pnl_r > 0 sur trades bloqués ⇒ le filtre a écarté des winners."
        ),
    }


def list_shadows(
    session: Session,
    *,
    portfolio_id: str | None = None,
    status: str | None = None,
    limit: int = 50,
) -> list[ShadowPosition]:
    q = select(ShadowPosition).order_by(ShadowPosition.created_at.desc()).limit(limit)
    if portfolio_id:
        q = q.where(ShadowPosition.portfolio_id == portfolio_id)
    if status:
        q = q.where(ShadowPosition.status == status)
    return list(session.execute(q).scalars())


def shadow_to_dict(sh: ShadowPosition) -> dict[str, Any]:
    return {
        "id": sh.id,
        "portfolio_id": sh.portfolio_id,
        "symbol": sh.symbol,
        "timeframe": sh.timeframe,
        "direction": sh.direction,
        "status": sh.status,
        "entry_time": sh.entry_time.isoformat() if sh.entry_time else None,
        "entry_price": sh.entry_price,
        "stop_price": sh.stop_price,
        "take_profit_price": sh.take_profit_price,
        "exit_time": sh.exit_time.isoformat() if sh.exit_time else None,
        "exit_price": sh.exit_price,
        "exit_reason": sh.exit_reason,
        "pnl_r": sh.pnl_r,
        "pnl_pct": sh.pnl_pct,
        "block_source": sh.block_source,
        "block_reason": sh.block_reason,
        "raw_decision": sh.raw_decision,
    }
