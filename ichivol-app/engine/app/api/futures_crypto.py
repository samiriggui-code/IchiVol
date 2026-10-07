"""Futures & Crypto portfolio view (YM, MGC, BTC) and its BTC instrument setting.

Read side: per market, what is traded (contract, price source and its limits), the last verdict the 1h loop
handed to this portfolio, realized P&L of closed trades, and the global open-risk cap. Open positions, marks and the equity curve
come from the regular portfolio overview (/paper/portfolios/{code}/overview); the page joins both.

Write side: the BTC mode (spot / perpetual / CME), stored on the portfolio profile. Refused while a BTC lot is
open, so a lot is never re-labelled to an instrument it was not opened on.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from app.config import settings
from app.db.models import PaperJournalEvent, PaperPosition
from app.db.session import SessionLocal
from app.paper import futures_crypto as fc
from app.paper.portfolio import ensure_portfolio

router = APIRouter(prefix=settings.engine_api_prefix, tags=["engine"])

BTC_MODE_EVENT = "BTC_MODE_CHANGED"


def _costs(profile: dict, symbol: str) -> dict:
    return {
        "commission_bps": float((profile.get("commission_bps_by_symbol") or {}).get(symbol, profile.get("commission_bps", 0.0))),
        "friction_bps": float((profile.get("friction_bps_by_symbol") or {}).get(symbol, 0.0)),
        "financing_bps_per_day_long": float((profile.get("financing_bps_per_day_by_symbol") or {}).get(symbol, 0.0)),
    }


def build_view(session) -> dict:
    portfolio = ensure_portfolio(session, fc.FUTURES_CRYPTO_CODE)
    profile = dict(portfolio.strategy_profile or {})
    positions = session.execute(
        select(PaperPosition).where(PaperPosition.portfolio_id == portfolio.id)
    ).scalars().all()

    markets = []
    for m in fc.markets_for(profile):
        sym = m["symbol"]
        closed = [p for p in positions if p.symbol == sym and p.status == "CLOSED" and p.realized_pnl is not None]
        markets.append({
            **m,
            "open": any(p.symbol == sym and p.status == "OPEN" for p in positions),
            "closed_trades": len(closed),
            "wins": sum(1 for p in closed if float(p.realized_pnl or 0.0) > 0),
            "realized_pnl": round(sum(float(p.realized_pnl or 0.0) for p in closed), 2),
            "last_signal": fc.last_signal(sym),
            "costs": _costs(profile, sym),
        })

    # Lots still open on a symbol of another BTC mode (cannot happen through the API, which refuses the change
    # while a BTC lot is open, but a lot opened before a manual DB edit stays visible rather than hidden).
    current = set(fc.traded_symbols(profile))
    orphans = sorted({p.symbol for p in positions if p.status == "OPEN" and p.symbol not in current})

    return {
        "code": portfolio.code,
        "label": portfolio.label,
        "btc_mode": fc.btc_mode(profile),
        "btc_modes": [
            {k: v[k] for k in ("mode", "symbol", "name", "venue", "contract", "contract_unit", "price_source", "price_note")}
            for v in fc.BTC_VARIANTS.values()
        ],
        "btc_mode_locked": any(p.symbol in {v["symbol"] for v in fc.BTC_VARIANTS.values()} and p.status == "OPEN" for p in positions),
        "markets": markets,
        "other_open_symbols": orphans,
        "rules": {
            "timeframe": "1h",
            "entry": "Signal IchiVol (Ichimoku × RVOL) sur la boucle 1h, comme le portefeuille IchiVol",
            "allow_short": bool(profile.get("allow_short", False)),
            "risk_pct": float(profile.get("risk_pct", 0.005)),
            "max_open_risk_pct": float(profile.get("max_open_risk_pct", 0.01)),
            "max_notional_pct": float(profile.get("max_notional_pct", 0.30)),
            "max_open_positions": int(profile.get("max_open_positions", 3)),
            "daily_loss_limit_pct": float(profile.get("daily_loss_limit_pct", 0.03)),
        },
    }


@router.get("/paper/futures-crypto")
def get_futures_crypto_view() -> dict:
    session = SessionLocal()
    try:
        view = build_view(session)
        session.commit()
        return view
    finally:
        session.close()


class BtcModeBody(BaseModel):
    mode: str


@router.post("/paper/futures-crypto/btc-mode")
def post_futures_crypto_btc_mode(body: BtcModeBody) -> dict:
    if body.mode not in fc.BTC_MODES:
        raise HTTPException(status_code=422, detail=f"unknown_btc_mode: {body.mode}")
    session = SessionLocal()
    try:
        portfolio = ensure_portfolio(session, fc.FUTURES_CRYPTO_CODE)
        profile = dict(portfolio.strategy_profile or {})
        before = fc.btc_mode(profile)
        if body.mode != before:
            btc_symbols = {v["symbol"] for v in fc.BTC_VARIANTS.values()}
            held = session.execute(
                select(PaperPosition.symbol).where(
                    PaperPosition.portfolio_id == portfolio.id,
                    PaperPosition.status == "OPEN",
                    PaperPosition.symbol.in_(btc_symbols),
                )
            ).scalars().first()
            if held is not None:
                raise HTTPException(
                    status_code=409,
                    detail=f"btc_position_open: close the open {held} lot before changing the BTC instrument",
                )
            portfolio.strategy_profile = fc.with_btc_mode(profile, body.mode)
            now = datetime.now(timezone.utc)
            session.add(PaperJournalEvent(
                portfolio_id=portfolio.id, position_id=None, event_type=BTC_MODE_EVENT,
                payload={"before": before, "after": body.mode, "effective_at": now.isoformat()},
                created_at=now,
            ))
        session.commit()
        return build_view(session)
    finally:
        session.close()
