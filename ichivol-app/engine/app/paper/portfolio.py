"""Paper portfolio bootstrap / lookup."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import PaperPortfolio
from app.paper.strategy_profiles import (
    ALL_PROFILES,
    MAIN_CODE,
    RETIRED_CODES,
    profile_for,
    syncable_profile_codes,
)

PROFILE_SYNC_EVENT = "PROFILE_SYNC"


class RetiredPortfolioError(LookupError):
    """Un code de compte retiré (2026-10-27) a été demandé pour trader."""


def ensure_main_portfolio(session: Session) -> PaperPortfolio:
    """Le portefeuille unique, créé à 50 000 € au premier appel.

    Son profil stocké est réaligné sur le profil du code (MAIN_PROFILE) quand il diffère, sans toucher à la
    caisse ni au capital de départ, et le changement est journalisé : le compte suit toujours le profil documenté
    (les anciens comptes gardaient un profil figé en base qui divergeait du code)."""
    portfolio = ensure_portfolio(session, MAIN_CODE)
    wanted = profile_for(MAIN_CODE)
    current = dict(portfolio.strategy_profile or {})
    if current != wanted:
        from app.db.models import PaperJournalEvent

        changed = sorted(k for k in set(current) | set(wanted) if current.get(k) != wanted.get(k))
        portfolio.strategy_profile = wanted
        portfolio.label = str(wanted.get("label") or MAIN_CODE)
        now = datetime.now(timezone.utc)
        session.add(PaperJournalEvent(
            portfolio_id=portfolio.id, position_id=None, event_type=PROFILE_SYNC_EVENT,
            payload={"changed_keys": changed, "effective_at": now.isoformat(),
                     "note": "profil stocké réaligné sur MAIN_PROFILE (strategy_profiles.py)"},
            created_at=now,
        ))
        session.flush()
    return portfolio


def resolve_trading_portfolio(session: Session, code: str | None) -> PaperPortfolio | None:
    """Compte visé par un ordre (manuel, Ève, agent). Vide → le compte unique ; code retiré → erreur ;
    code inconnu → None (les tests peuvent encore viser un compte jetable existant)."""
    if not code or code == MAIN_CODE:
        return ensure_main_portfolio(session)
    if code in RETIRED_CODES:
        raise RetiredPortfolioError(code)
    return get_portfolio_by_code(session, code)


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
    # (Avant 2026-10-27, le compte baseline adoptait les lots sans portefeuille ; le compte unique part vide.)
    return portfolio


def ensure_syncable_portfolios(session: Session) -> list[PaperPortfolio]:
    """Le(s) compte(s) synchronisé(s) : le portefeuille unique seulement depuis le 2026-10-27."""
    return [ensure_main_portfolio(session) if code == MAIN_CODE else ensure_portfolio(session, code)
            for code in syncable_profile_codes()]


def get_portfolio_by_code(session: Session, code: str) -> PaperPortfolio | None:
    return session.execute(
        select(PaperPortfolio).where(PaperPortfolio.code == code)
    ).scalar_one_or_none()


def list_portfolios(session: Session, *, active_only: bool = True) -> list[PaperPortfolio]:
    """Comptes affichés comme actifs. ``active_only`` : le compte unique seulement (un ancien compte encore en
    base avant le script de suppression n'est jamais présenté comme actif, même si ``is_active`` est vrai)."""
    stmt = select(PaperPortfolio).order_by(PaperPortfolio.started_at.asc())
    if active_only:
        stmt = stmt.where(
            PaperPortfolio.is_active.is_(True),
            PaperPortfolio.code.in_(syncable_profile_codes()),
        )
    return list(session.execute(stmt).scalars().all())


def known_profile_codes() -> list[str]:
    return list(ALL_PROFILES.keys())


def lookup_portfolio(session: Session, code: str) -> PaperPortfolio | None:
    """Lecture d'un compte par code pour les vues : le compte unique est créé s'il manque (premier démarrage),
    un ancien compte encore en base reste lisible (historique) mais n'est JAMAIS recréé."""
    if code == MAIN_CODE:
        portfolio = ensure_main_portfolio(session)
        session.commit()
        return portfolio
    return get_portfolio_by_code(session, code)
