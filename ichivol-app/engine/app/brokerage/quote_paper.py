"""Quote-based paper entry/exit: fetch a real bid/ask, then let the broker fill on it.

Opt-in path -- the legacy candle/bps flow in ``app.paper.engine`` is untouched.
Refuses (returns None) when the quote is missing or stale instead of falling
back to a made-up price.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.db.models import PaperPortfolio, PaperPosition
from app.market_data.contracts import Quote, QuoteProvider
from app.paper import broker
from app.universe.catalog import get_instrument

MAX_QUOTE_AGE_SECONDS = 5.0


def _fresh_quote(provider: QuoteProvider, symbol: str, now: datetime) -> Quote | None:
    try:
        quote = provider.fetch_quote(symbol)
    except Exception:
        return None
    # Clock skew makes latency negative on a fast exchange clock; only a
    # clearly old quote is rejected.
    age = (now - quote.provenance.received_at).total_seconds()
    return quote if age <= MAX_QUOTE_AGE_SECONDS else None


def open_at_market(
    session: Session,
    *,
    portfolio: PaperPortfolio,
    provider: QuoteProvider,
    instrument_id: str,
    timeframe: str,
    direction: str,
    decision: str,
    stop_distance: float,
    signal: dict[str, Any] | None = None,
    now: datetime | None = None,
) -> PaperPosition | None:
    instrument = get_instrument(instrument_id)
    if instrument is None or not instrument.is_wired or instrument.provider != provider.id:
        return None
    quote = _fresh_quote(provider, instrument.provider_symbol, now or datetime.now(timezone.utc))
    if quote is None:
        return None
    return broker.open_capital_position(
        session,
        portfolio=portfolio,
        symbol=instrument.id,
        timeframe=timeframe,
        source="quote_paper",
        user_id=None,
        direction=direction,
        price=quote.mid,
        decision=decision,
        stop_distance=stop_distance,
        signal=signal,
        quote=quote,
    )


def close_at_market(
    session: Session,
    position: PaperPosition,
    *,
    provider: QuoteProvider,
    reason: str,
    now: datetime | None = None,
) -> PaperPosition | None:
    instrument = get_instrument(position.symbol)
    if instrument is None or not instrument.is_wired:
        return None
    quote = _fresh_quote(provider, instrument.provider_symbol, now or datetime.now(timezone.utc))
    if quote is None:
        return None
    return broker.close_capital_position(session, position, price=quote.mid, reason=reason, quote=quote)
