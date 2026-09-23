"""API — typed ChartObjects for chart overlays (T2a + T2b store merge).

GET /chart-objects/{symbol} returns drawable objects from ENGINE (structure)
plus persisted USER / CLAUDE overlays when those sources are requested.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Header, HTTPException, Query

from app.chart_objects.collect import collect_chart_objects
from app.config import settings
from app.market_data.resolve import ProviderNotWiredError

router = APIRouter(prefix=settings.engine_api_prefix, tags=["engine"])


@router.get("/chart-objects/{symbol}")
def get_chart_objects(
    symbol: str,
    timeframe: str = "1h",
    limit: int = Query(300, ge=1, le=500),
    sources: str = Query(
        "engine",
        description="Comma-separated ChartObjectSource values (engine,user,claude,strategy,backtest)",
    ),
    include_pytrendline: bool = False,
    x_twelve_data_key: str | None = Header(default=None, alias="X-Twelve-Data-Key"),
) -> dict[str, Any]:
    """Typed chart overlays: ENGINE from structure; USER/CLAUDE from store (T2b).

    STRATEGY / BACKTEST sources return empty until T4/T5. No real orders.
    """
    try:
        return collect_chart_objects(
            symbol=symbol,
            timeframe=timeframe,
            limit=limit,
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
