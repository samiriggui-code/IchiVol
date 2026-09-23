"""API — typed ChartObjects for chart overlays (T2a + T2b store + T2c USER write).

GET /chart-objects/{symbol} returns drawable objects from ENGINE (structure)
plus persisted USER / CLAUDE overlays when those sources are requested.

POST /chart-objects/{symbol} persists USER ENTRY/STOP/TARGET (T2c).
DELETE /chart-objects/item/{object_id} soft-deletes USER overlays only.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Body, Header, HTTPException, Query

from app.chart_objects.collect import collect_chart_objects
from app.chart_objects.user_write import (
    UserWriteError,
    delete_user_chart_object,
    persist_user_trade_object,
)
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


@router.post("/chart-objects/{symbol}")
def post_user_chart_object(
    symbol: str,
    body: dict[str, Any] = Body(...),
    x_twelve_data_key: str | None = Header(default=None, alias="X-Twelve-Data-Key"),
) -> dict[str, Any]:
    """Persist a USER trade point (entry|stop|target). Source is always forced to user.

    Optional ``setup_id`` groups ENTRY/STOP/TARGET of one mark-trade session.
    Points are grounded against real OHLCV (same rules as agent draw_*).
    """
    try:
        return persist_user_trade_object(
            symbol,
            body if isinstance(body, dict) else {},
            x_twelve_data_key=x_twelve_data_key,
        )
    except UserWriteError as exc:
        detail = str(exc)
        if detail.startswith("not_found"):
            raise HTTPException(status_code=404, detail=detail) from exc
        if detail.startswith("point_not_grounded") or "ProviderNotWired" in detail:
            raise HTTPException(status_code=422, detail=detail) from exc
        # Provider not wired messages often look like plain strings.
        lower = detail.lower()
        if "not wired" in lower or "provider" in lower and "not" in lower:
            raise HTTPException(status_code=404, detail=detail) from exc
        if detail.startswith("persist_failed"):
            raise HTTPException(status_code=500, detail=detail) from exc
        raise HTTPException(status_code=422, detail=detail) from exc


@router.delete("/chart-objects/item/{object_id}")
def delete_user_chart_object_route(object_id: str) -> dict[str, Any]:
    """Soft-delete a USER chart overlay. Does not delete CLAUDE/ENGINE objects."""
    try:
        return delete_user_chart_object(object_id)
    except UserWriteError as exc:
        detail = str(exc)
        if detail.startswith("not_found"):
            raise HTTPException(status_code=404, detail=detail) from exc
        if detail.startswith("delete_failed"):
            raise HTTPException(status_code=500, detail=detail) from exc
        raise HTTPException(status_code=422, detail=detail) from exc
