"""API — IndicatorRegistry catalog + per-symbol series (read-only)."""

from __future__ import annotations

import json
from dataclasses import asdict, fields as dc_fields, is_dataclass
from typing import Any

from fastapi import APIRouter, Header, HTTPException, Query

from app.config import settings
from app.indicators.registry import (
    REGISTRY,
    InvalidParamsError,
    UnknownIndicatorError,
    serialize_state,
)
from app.market_data import twelve_data

router = APIRouter(prefix=settings.engine_api_prefix, tags=["indicators"])


@router.get("/indicators")
def list_indicators() -> dict[str, Any]:
    return {"indicators": REGISTRY.catalog()}


@router.get("/indicators/ichimoku/{symbol}/projection")
def get_ichimoku_projection(
    symbol: str,
    timeframe: str = "1h",
    limit: int = Query(300, ge=1, le=5000),
    params: str | None = Query(default=None, description="JSON object of IchimokuParams overrides"),
    x_twelve_data_key: str | None = Header(default=None, alias="X-Twelve-Data-Key"),
) -> dict[str, Any]:
    """Forward Kumo spans for chart display only (not a decision feature)."""
    from app.indicators.ichimoku import compute_projected_kumo
    from app.market_data.resolve import ProviderNotWiredError, resolve_and_fetch

    try:
        definition = REGISTRY.get("ichimoku")
    except UnknownIndicatorError as exc:
        raise HTTPException(status_code=404, detail=f"unknown_indicator: ichimoku") from exc

    overrides: dict[str, Any] = {}
    if params:
        try:
            parsed = json.loads(params)
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=422, detail=f"invalid params JSON: {exc}") from exc
        if not isinstance(parsed, dict):
            raise HTTPException(status_code=422, detail="params must be a JSON object")
        overrides = parsed

    try:
        built = definition.build_params(overrides)
    except InvalidParamsError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    warmup = definition.warmup(built)
    fetch_limit = max(1, int(limit) + warmup)

    twelve_data.set_api_key_override(x_twelve_data_key)
    try:
        provider, provider_symbol, candles = resolve_and_fetch(
            symbol.upper(), timeframe, fetch_limit
        )
    except ProviderNotWiredError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    # Compute on the full fetch (incl. warmup), then keep points that land on
    # or after the visible window start — plus extrapolated bars beyond the end.
    window = candles[-int(limit) :] if len(candles) > int(limit) else candles
    window_start = window[0].time if window else 0
    projection = [
        p
        for p in compute_projected_kumo(candles, built)
        if int(p["time_projected"]) >= window_start
    ]

    return {
        "indicator": "ichimoku",
        "kind": "projection",
        "symbol": symbol.upper(),
        "timeframe": timeframe,
        "provider": provider.id,
        "provider_symbol": provider_symbol,
        "params": {f.name: getattr(built, f.name) for f in dc_fields(built)},
        "displacement": built.displacement,
        "warmup": warmup,
        "projection": projection,
        "note": "display_only",
    }


@router.get("/indicators/{indicator_id}/{symbol}")
def get_indicator_series(
    indicator_id: str,
    symbol: str,
    timeframe: str = "1h",
    limit: int = Query(300, ge=1, le=5000),
    params: str | None = Query(default=None, description="JSON object of param overrides"),
    x_twelve_data_key: str | None = Header(default=None, alias="X-Twelve-Data-Key"),
) -> dict[str, Any]:
    """Compute an indicator series for a symbol via the global REGISTRY.

    Fetches ``limit + warmup`` candles so the returned ``limit`` states are
    fully warmed where possible. No formula rewrite — wraps existing compute_*.
    """
    from app.market_data.resolve import ProviderNotWiredError, resolve_and_fetch

    try:
        definition = REGISTRY.get(indicator_id)
    except UnknownIndicatorError as exc:
        raise HTTPException(status_code=404, detail=f"unknown_indicator: {indicator_id}") from exc

    overrides: dict[str, Any] = {}
    if params:
        try:
            parsed = json.loads(params)
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=422, detail=f"invalid params JSON: {exc}") from exc
        if not isinstance(parsed, dict):
            raise HTTPException(status_code=422, detail="params must be a JSON object")
        overrides = parsed

    try:
        built = definition.build_params(overrides)
    except InvalidParamsError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    warmup = definition.warmup(built)
    fetch_limit = max(1, int(limit) + warmup)

    twelve_data.set_api_key_override(x_twelve_data_key)
    try:
        provider, provider_symbol, candles = resolve_and_fetch(
            symbol.upper(), timeframe, fetch_limit
        )
    except ProviderNotWiredError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    states = REGISTRY.compute(indicator_id, candles, built)
    series = [serialize_state(s) for s in states[-int(limit) :]]

    params_out: dict[str, Any] = {}
    for f in dc_fields(built):
        val = getattr(built, f.name)
        if is_dataclass(val) and not isinstance(val, type):
            params_out[f.name] = asdict(val)
        else:
            params_out[f.name] = val

    return {
        "indicator": indicator_id,
        "symbol": symbol.upper(),
        "timeframe": timeframe,
        "provider": provider.id,
        "provider_symbol": provider_symbol,
        "params": params_out,
        "warmup": warmup,
        "primary_output": definition.primary_output,
        "series": series,
    }
