"""API — Chart Intelligence (OHLCV + Ichimoku + ChartObjects + market_state).

GET /chart-intelligence/{symbol}?timeframe&limit&as_of&sources
GET /chart-intelligence/{symbol}/replay?timeframe&from&to&lookback_bars
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Header, HTTPException, Query

from app.chart_intelligence.service import (
    build_chart_intelligence,
    build_chart_intelligence_replay,
)
from app.config import settings
from app.market_data.resolve import ProviderNotWiredError

router = APIRouter(prefix=settings.engine_api_prefix, tags=["engine"])


def _http_map(exc: Exception) -> HTTPException:
    if isinstance(exc, ProviderNotWiredError):
        return HTTPException(status_code=404, detail=str(exc))
    if isinstance(exc, ValueError):
        detail = str(exc)
        if detail.startswith("invalid_source"):
            return HTTPException(status_code=422, detail=detail)
        return HTTPException(status_code=404, detail=detail)
    return HTTPException(status_code=500, detail=str(exc))


@router.get("/chart-intelligence/{symbol}/replay")
def get_chart_intelligence_replay(
    symbol: str,
    timeframe: str = "1h",
    limit: int = Query(300, ge=1, le=500),
    from_ts: int | None = Query(default=None, alias="from"),
    to_ts: int | None = Query(default=None, alias="to"),
    lookback_bars: int = Query(48, ge=2, le=120),
    sources: str = Query("engine", description="Comma-separated ChartObjectSource values"),
    include_pytrendline: bool = False,
    x_twelve_data_key: str | None = Header(default=None, alias="X-Twelve-Data-Key"),
) -> dict[str, Any]:
    """Walk-forward replay pack (CI-R1a) — objects recalculated bar-by-bar."""
    try:
        return build_chart_intelligence_replay(
            symbol=symbol,
            timeframe=timeframe,
            limit=limit,
            from_ts=from_ts,
            to_ts=to_ts,
            lookback_bars=lookback_bars,
            sources=sources,
            include_pytrendline=include_pytrendline,
            x_twelve_data_key=x_twelve_data_key,
        )
    except (ProviderNotWiredError, ValueError) as exc:
        raise _http_map(exc) from exc


@router.get("/chart-intelligence/{symbol}")
def get_chart_intelligence(
    symbol: str,
    timeframe: str = "1h",
    limit: int = Query(300, ge=1, le=500),
    as_of: int | None = Query(
        default=None,
        description="Unix seconds — recompute on candles with time <= as_of",
    ),
    sources: str = Query(
        "engine,user,claude",
        description="Comma-separated ChartObjectSource values",
    ),
    include_pytrendline: bool = False,
    x_twelve_data_key: str | None = Header(default=None, alias="X-Twelve-Data-Key"),
) -> dict[str, Any]:
    """Live Chart Intelligence snapshot for the React panel (not mock)."""
    try:
        return build_chart_intelligence(
            symbol=symbol,
            timeframe=timeframe,
            limit=limit,
            as_of=as_of,
            sources=sources,
            include_pytrendline=include_pytrendline,
            x_twelve_data_key=x_twelve_data_key,
        )
    except (ProviderNotWiredError, ValueError) as exc:
        raise _http_map(exc) from exc
