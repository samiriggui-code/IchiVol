"""Paper portfolio bootstrap / lookup."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.db.models import PaperPortfolio, PaperPosition
from app.paper.strategy_profiles import (
    ALL_PROFILES,
    BASELINE_CODE,
    profile_for,
    syncable_profile_codes,
)


def ensure_baseline_portfolio(session: Session) -> PaperPortfolio:
    return ensure_portfolio(session, BASELINE_CODE)


def ensure_portfolio(session: Session, code: str) -> PaperPortfolio:
    existing = session.execute(
        select(PaperPortfolio).where(PaperPortfolio.code == code)
    ).scalar_one_or_none()
    if existing is not None:
        return existing

    profile = profile_for(code)
    now = datetime.now(timezone.utc)
    portfolio = PaperPortfolio(
        code=code,
        label=str(profile.get("label") or code),
        currency="EUR",
        valuation_mode=str(profile.get("valuation_mode", "USDT_AS_EUR_PROXY")),
        initial_cash=float(profile.get("initial_cash_eur", 5000.0)),
        cash=float(profile.get("initial_cash_eur", 5000.0)),
        realized_pnl=0.0,
        strategy_profile=dict(profile),
        is_active=True,
        started_at=now,
        created_at=now,
        updated_at=now,
    )
    session.add(portfolio)
    session.flush()

    if code == BASELINE_CODE:
        session.execute(
            update(PaperPosition)
            .where(PaperPosition.portfolio_id.is_(None))
            .values(portfolio_id=portfolio.id)
        )
        session.flush()
    return portfolio


def ensure_syncable_portfolios(session: Session) -> list[PaperPortfolio]:
    """Seed baseline + STRUCTURE_* / ICHIVOL_MS_V1 experimental accounts."""
    return [ensure_portfolio(session, code) for code in syncable_profile_codes()]


def get_portfolio_by_code(session: Session, code: str) -> PaperPortfolio | None:
    return session.execute(
        select(PaperPortfolio).where(PaperPortfolio.code == code)
    ).scalar_one_or_none()


def list_portfolios(session: Session, *, active_only: bool = True) -> list[PaperPortfolio]:
    stmt = select(PaperPortfolio).order_by(PaperPortfolio.started_at.asc())
    if active_only:
        stmt = stmt.where(PaperPortfolio.is_active.is_(True))
    return list(session.execute(stmt).scalars().all())


def known_profile_codes() -> list[str]:
    return list(ALL_PROFILES.keys())
