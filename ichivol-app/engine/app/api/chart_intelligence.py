"""API — Chart Intelligence (OHLCV + Ichimoku + ChartObjects + market_state).

GET /chart-intelligence/{symbol}?timeframe&limit&as_of&sources
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Header, HTTPException, Query

from app.chart_intelligence.service import build_chart_intelligence
from app.config import settings
from app.market_data.resolve import ProviderNotWiredError

router = APIRouter(prefix=settings.engine_api_prefix, tags=["engine"])


@router.get("/chart-intelligence/{symbol}")
def get_chart_intelligence(
    symbol: str,
    timeframe: str = "1h",
    limit: int = Query(300, ge=1, le=500),
    as_of: int | None = Query(
        default=None,
        description="Unix seconds — recompute on candles with time <= as_of (anti-lookahead)",
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
    except ProviderNotWiredError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        detail = str(exc)
        if detail.startswith("invalid_source"):
            raise HTTPException(status_code=422, detail=detail) from exc
        raise HTTPException(status_code=404, detail=detail) from exc
