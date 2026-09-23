"""API — typed ChartObjects for chart overlays (T2a).

GET /chart-objects/{symbol} returns drawable objects produced by the engine.
Only ``ENGINE`` source is produced today; other requested sources yield an
empty contribution (not an error).
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Header, HTTPException, Query

from app.chart_objects.from_structure import structure_to_chart_objects
from app.chart_objects.types import ChartObjectSource
from app.config import settings
from app.market_data import twelve_data
from app.structure.params import StructureEngineParams
from app.structure.service import detect_market_structure

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
    """Typed chart overlays derived from Market Structure (ENGINE source).

    Non-engine sources requested in ``sources`` return no objects (empty list
    contribution) until T2b/T5 persistence lands. No real orders — analysis only.
    """
    from app.market_data.resolve import ProviderNotWiredError, resolve_and_fetch

    requested: list[str] = []
    for part in sources.split(","):
        raw = part.strip().lower()
        if not raw:
            continue
        try:
            requested.append(ChartObjectSource(raw).value)
        except ValueError as exc:
            raise HTTPException(
                status_code=422,
                detail=f"invalid_source: {raw!r}",
            ) from exc
    if not requested:
        requested = [ChartObjectSource.ENGINE.value]

    objects: list[dict[str, Any]] = []
    provider: str | None = None
    provider_symbol: str | None = None
    as_of: int | None = None

    if ChartObjectSource.ENGINE.value in requested:
        twelve_data.set_api_key_override(x_twelve_data_key)
        try:
            prov, provider_symbol, candles = resolve_and_fetch(
                symbol.upper(), timeframe, min(limit, 500)
            )
        except ProviderNotWiredError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

        provider = prov.id
        params = StructureEngineParams(window_bars=min(limit, 500))
        snap = detect_market_structure(
            candles, params, include_pytrendline=include_pytrendline
        )
        window = list(candles[-params.window_bars :])
        as_of = int(window[-1].time) if window else None
        objects.extend(
            o.to_dict()
            for o in structure_to_chart_objects(
                snap, symbol.upper(), timeframe, window
            )
        )

    # USER / CLAUDE / STRATEGY / BACKTEST — not produced yet (empty, not error).

    return {
        "symbol": symbol.upper(),
        "timeframe": timeframe,
        "provider": provider,
        "provider_symbol": provider_symbol,
        "as_of": as_of,
        "sources": requested,
        "objects": objects,
        "count": len(objects),
    }
