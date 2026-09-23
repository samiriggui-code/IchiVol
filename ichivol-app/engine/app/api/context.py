"""Context surface: news, calendar, per-symbol indicators."""

from __future__ import annotations

from fastapi import APIRouter, Header, HTTPException

from app.config import settings
from app.context.calendar import fetch_calendar_events
from app.context.news import fetch_news
from app.indicators.registry import REGISTRY
from app.market_data import twelve_data

router = APIRouter(prefix=settings.engine_api_prefix, tags=["engine"])

@router.get("/context/news")
def get_context_news(limit: int = 20, sources: str | None = None) -> dict:
    """Read-only crypto news headlines (CDC "adapters context", V3, opt-in)
    -- free/keyless RSS, never wired into the decision pipeline (see
    app/context/news.py). `sources` (comma-separated) restricts to a subset
    of `news.FEEDS`; omit for all of them. One feed failing never empties
    the others -- worst case this returns `[]`, never a 502."""
    source_list = [s.strip() for s in sources.split(",") if s.strip()] if sources else None
    items = fetch_news(limit=limit, sources=source_list)
    return {
        "items": [
            {"title": i.title, "url": i.url, "source": i.source, "published_at": i.published_at}
            for i in items
        ]
    }


@router.get("/context/calendar")
def get_context_calendar(limit: int | None = None) -> dict:
    """Read-only macro economic calendar, this week (CDC "adapters context",
    V3, opt-in) -- free/keyless community feed, never wired into the
    decision pipeline (see app/context/calendar.py). Degrades to an empty
    list on any upstream failure, never a 502."""
    events = fetch_calendar_events(limit=limit)
    return {
        "events": [
            {
                "title": e.title, "country": e.country, "date": e.date,
                "impact": e.impact, "forecast": e.forecast, "previous": e.previous,
            }
            for e in events
        ]
    }


@router.get("/context/{symbol}")
def get_context_indicators(
    symbol: str,
    timeframe: str = "1h",
    limit: int = 300,
    x_twelve_data_key: str | None = Header(default=None, alias="X-Twelve-Data-Key"),
) -> dict:
    """Phase 3 context snapshot: RSI + CMF + OBV + ATR regime (analysis only)."""
    from app.market_data.resolve import ProviderNotWiredError, resolve_and_fetch

    twelve_data.set_api_key_override(x_twelve_data_key)
    try:
        provider, provider_symbol, candles = resolve_and_fetch(
            symbol.upper(), timeframe, min(limit, 500)
        )
    except ProviderNotWiredError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    computed = REGISTRY.compute_many(["rsi", "cmf", "obv", "atr"], candles)
    rsi = computed["rsi"][-1]
    cmf = computed["cmf"][-1]
    obv = computed["obv"][-1]
    atr = computed["atr"][-1]
    return {
        "symbol": symbol.upper(),
        "timeframe": timeframe,
        "provider": provider.id,
        "provider_symbol": provider_symbol,
        "last_close": candles[-1].close,
        "rsi": {"value": rsi.rsi, "bias": rsi.bias.value},
        "cmf": {"value": cmf.cmf, "bias": cmf.bias.value},
        "obv": {"value": obv.obv, "bias": obv.bias.value, "slope": obv.slope},
        "atr": {
            "value": atr.atr,
            "regime": atr.regime.value,
            "suggested_stop_distance": atr.suggested_stop_distance,
        },
    }

