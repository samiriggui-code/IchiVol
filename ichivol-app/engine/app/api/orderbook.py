"""API — OB-1 carnet d'ordres collecté (lecture seule des fichiers du service orderbook-collector).

GET /orderbook/status
GET /orderbook/{symbol}/minutes?from=<unix>&to=<unix>&limit=<n>
GET /orderbook/{symbol}/quality?hours=<n>

Observe-only : aucune donnée de carnet n'entre dans le pipeline, le paper ou les gates.
"""

from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter, HTTPException, Query

from app.config import settings
from app.microstructure.book import read as ob_read

router = APIRouter(prefix=settings.engine_api_prefix, tags=["engine"])


@router.get("/orderbook/status")
def get_orderbook_status() -> dict[str, Any]:
    return ob_read.status_all(settings.ob_data_dir)


@router.get("/orderbook/{symbol}/minutes")
def get_orderbook_minutes(
    symbol: str,
    from_: int | None = Query(default=None, alias="from", description="Unix seconds (défaut : maintenant − 2 h)"),
    to: int | None = Query(default=None, description="Unix seconds, exclu (défaut : maintenant)"),
    limit: int = Query(240, ge=1, le=4320),
) -> dict[str, Any]:
    now = int(time.time())
    end = now if to is None else int(to)
    start = end - 2 * 3600 if from_ is None else int(from_)
    if start >= end:
        raise HTTPException(status_code=422, detail="from must be < to")
    return ob_read.minutes(settings.ob_data_dir, symbol, start, end, limit)


@router.get("/orderbook/{symbol}/quality")
def get_orderbook_quality(symbol: str, hours: int = Query(24, ge=1, le=168)) -> dict[str, Any]:
    return ob_read.quality(settings.ob_data_dir, symbol, hours)
