"""AG-S1 — fiches analystes + snapshots de session (lecture / écriture observe-only)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Header, HTTPException, Query
from pydantic import BaseModel, Field

from app.agents.analyst_cards import build_analyst_cards
from app.agents.analyst_snapshot import get_analyst_snapshot, take_session_snapshot
from app.config import settings
from app.market_data.resolve import ProviderNotWiredError

router = APIRouter(prefix=settings.engine_api_prefix, tags=["agents"])


class SnapshotBody(BaseModel):
    session_id: str = Field(min_length=3, max_length=64)
    symbol: str = Field(min_length=3, max_length=32)
    timeframe: str = Field(default="1h", min_length=2, max_length=8)
    limit: int = Field(default=500, ge=50, le=1000)


@router.get("/agents/analyst-cards")
def get_analyst_cards(
    symbol: str = Query(..., min_length=3, max_length=32),
    timeframe: str = Query("1h", min_length=2, max_length=8),
    limit: int = Query(500, ge=50, le=1000),
    as_of: int | None = Query(default=None, description="Unix seconds — barre close"),
    now: int | None = Query(default=None, description="Unix seconds (tests closed-bar)"),
    x_twelve_data_key: str | None = Header(default=None, alias="X-Twelve-Data-Key"),
) -> dict[str, Any]:
    """Fiches analystes déterministes (observe-only, used_by_decision=False)."""
    try:
        return build_analyst_cards(
            symbol,
            timeframe,
            limit=limit,
            as_of=as_of,
            now=now,
            x_twelve_data_key=x_twelve_data_key,
        )
    except ProviderNotWiredError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.post("/agents/analyst-snapshots")
def post_analyst_snapshot(
    body: SnapshotBody,
    x_twelve_data_key: str | None = Header(default=None, alias="X-Twelve-Data-Key"),
) -> dict[str, Any]:
    """Écrit un snapshot de session (idempotent). Appelé par AgentTask +60 s."""
    try:
        return take_session_snapshot(
            session_id=body.session_id,
            symbol=body.symbol,
            timeframe=body.timeframe,
            limit=body.limit,
            x_twelve_data_key=x_twelve_data_key,
        )
    except ProviderNotWiredError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@router.get("/agents/analyst-snapshots")
def get_analyst_snapshot_route(
    session_id: str = Query(..., min_length=3, max_length=64),
    symbol: str = Query(..., min_length=3, max_length=32),
    timeframe: str = Query("1h", min_length=2, max_length=8),
) -> dict[str, Any]:
    row = get_analyst_snapshot(
        session_id=session_id, symbol=symbol, timeframe=timeframe
    )
    if row is None:
        raise HTTPException(status_code=404, detail="snapshot_not_found")
    return {"snapshot": row, "observe_only": True, "used_by_decision": False}
