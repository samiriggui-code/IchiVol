"""Market data surface: universe, OHLCV, structure, screener, correlations."""

from __future__ import annotations

import time

from fastapi import APIRouter, Header, HTTPException

from app.api.common import _atr_params_override, _line_dict, _rvol_params_override, _zone_dict
from app.api.serializers import metrics_dict, summary_dict
from app.config import settings
from app.correlation.engine import compute_correlation_matrix
from app.market_data import twelve_data
from app.screener.cache import screener_cache
from app.screener.service import scan_watchlist
from app.structure.params import StructureEngineParams
from app.structure.service import detect_market_structure
from app.universe.catalog import UNIVERSE, default_watchlist
from app.universe.types import AssetClass

router_head = APIRouter(prefix=settings.engine_api_prefix, tags=["engine"])
router_screener = APIRouter(prefix=settings.engine_api_prefix, tags=["engine"])
router_correlations = APIRouter(prefix=settings.engine_api_prefix, tags=["engine"])

_MAX_CORRELATION_SYMBOLS = 40

@router_head.get("/universe")
def get_universe() -> dict:
    """The full instrument catalog (docs/HANDOFF-CLAUDE-UNIVERSE-SKELETON.md):
    every asset class the product covers, not just the one with a wired
    provider today. `wired: false` entries have no data behind them yet --
    that's the point, not a bug (see app/universe/catalog.py)."""
    return {
        "classes": [c.value for c in AssetClass],
        "instruments": [
            {
                "id": i.id,
                "asset_class": i.asset_class.value,
                "label": i.label,
                "provider": i.provider,
                "provider_symbol": i.provider_symbol,
                "wired": i.is_wired,
                "enabled": i.enabled,
                "quote": i.quote,
            }
            for i in UNIVERSE
        ],
    }


@router_head.get("/ohlcv/{symbol}")
def get_ohlcv(
    symbol: str,
    timeframe: str = "1h",
    limit: int = 300,
    x_twelve_data_key: str | None = Header(default=None, alias="X-Twelve-Data-Key"),
) -> dict:
    """Neutral OHLCV for chart / front — resolves via catalog (binance, twelve_data, or biquote).
    `x_twelve_data_key`, when present, overrides the operator's
    TWELVE_DATA_API_KEY for this request only -- see app/market_data/twelve_data.py."""
    from app.market_data.resolve import ProviderNotWiredError, resolve_and_fetch

    twelve_data.set_api_key_override(x_twelve_data_key)
    try:
        provider, provider_symbol, candles = resolve_and_fetch(symbol.upper(), timeframe, limit)
    except ProviderNotWiredError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return {
        "symbol": symbol.upper(),
        "timeframe": timeframe,
        "provider": provider.id,
        "provider_symbol": provider_symbol,
        "candles": [
            {
                "time": c.time,
                "open": c.open,
                "high": c.high,
                "low": c.low,
                "close": c.close,
                "volume": c.volume,
            }
            for c in candles
        ],
    }


@router_head.get("/structure/{symbol}")
def get_structure(
    symbol: str,
    timeframe: str = "1h",
    limit: int = 300,
    include_pytrendline: bool = False,
    x_twelve_data_key: str | None = Header(default=None, alias="X-Twelve-Data-Key"),
) -> dict:
    """Market Structure Phase 2: MVPP + trendln consensus zones.

    ``include_pytrendline=true`` runs the capped offline detector (not for
    hot-path screener loops). No real orders — analysis only.
    """
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

    params = StructureEngineParams(window_bars=min(limit, 500))
    snap = detect_market_structure(
        candles, params, include_pytrendline=include_pytrendline
    )
    consensus = snap.consensus
    window = list(candles[-params.window_bars :])
    return {
        "symbol": symbol.upper(),
        "timeframe": timeframe,
        "provider": provider.id,
        "provider_symbol": provider_symbol,
        "atr": snap.atr,
        "last_close": snap.last_close,
        "distance_to_support": snap.distance_to_support,
        "distance_to_resistance": snap.distance_to_resistance,
        "consensus": {
            "structure_score": consensus.structure_score,
            "support_zones": [_zone_dict(z) for z in consensus.support_zones],
            "resistance_zones": [_zone_dict(z) for z in consensus.resistance_zones],
            "meta": consensus.meta,
        },
        "detectors": {
            name: {
                "structure_score": ms.structure_score,
                "support_zones": [_zone_dict(z) for z in ms.support_zones],
                "resistance_zones": [_zone_dict(z) for z in ms.resistance_zones],
                "support_trendlines": [_line_dict(t, window) for t in ms.support_trendlines],
                "resistance_trendlines": [_line_dict(t, window) for t in ms.resistance_trendlines],
                "pivot_count": len(ms.pivots),
                "meta": ms.meta,
            }
            for name, ms in snap.by_detector.items()
        },
        "breakout_candidates": [
            {
                "side": b.side.value,
                "confirmed": b.confirmed,
                "close": b.close,
                "distance_atr": b.distance_atr,
                "body_ratio": b.body_ratio,
                "rvol": b.rvol,
                "reason": b.reason,
                "zone": _zone_dict(b.zone),
            }
            for b in snap.breakout_candidates
        ],
    }


@router_screener.get("/screener")
def get_screener(
    timeframe: str = "1h",
    force: bool = False,
    rvol_low: float | None = None,
    rvol_significant: float | None = None,
    rvol_strong: float | None = None,
    rvol_anomaly: float | None = None,
    atr_dead_percentile: float | None = None,
    atr_extreme_percentile: float | None = None,
    atr_stop_multiplier: float | None = None,
) -> dict:
    """Serves the background-refreshed cache (see app/screener/cache.py) by
    default -- instant, no live Binance calls on the request path.
    `force=true` (wired to the frontend's "Rafraichir" button) triggers an
    on-demand recompute instead of waiting for the next scheduled refresh.
    Passing any RVOL/ATR threshold override always bypasses the shared cache
    (it's a per-caller reading, not the canonical scan the cache serves to
    everyone else) and is never persisted to the decision history.
    """
    has_overrides = any(
        v is not None
        for v in (
            rvol_low, rvol_significant, rvol_strong, rvol_anomaly,
            atr_dead_percentile, atr_extreme_percentile, atr_stop_multiplier,
        )
    )
    if has_overrides:
        rvol_params = _rvol_params_override(rvol_low, rvol_significant, rvol_strong, rvol_anomaly)
        atr_params = _atr_params_override(atr_dead_percentile, atr_extreme_percentile, atr_stop_multiplier)
        rows = scan_watchlist(timeframe=timeframe, rvol_params=rvol_params, atr_params=atr_params)
        return {
            "timeframe": timeframe,
            "computed_at": time.time(),
            "cache_age_seconds": 0.0,
            "rows": [summary_dict(r) for r in rows],
        }

    entry = None if force else screener_cache.get(timeframe)
    if entry is None:
        entry = screener_cache.refresh(timeframe)

    return {
        "timeframe": entry.timeframe,
        "computed_at": entry.computed_at,
        "cache_age_seconds": time.time() - entry.computed_at,
        "rows": [summary_dict(r) for r in entry.rows],
    }


@router_correlations.get("/correlations")
def get_correlations(
    timeframe: str = "1h",
    limit: int = 300,
    method: str = "log_returns",
    symbols: str | None = None,
) -> dict:
    """Correlation matrix (CDC §6.2 "Graphe de corrélations", `CDC-VIZ-002`,
    V2 optionnel) -- "qu'est-ce qui bouge avec BTC ?". Read-only lens, never
    wired into the decision pipeline, never a vote (docs/CAHIER-DES-CHARGES.md
    §8). Stateless like `/backtest`: recomputed on every call from whatever
    historical depth is available right now, nothing cached or persisted.

    `symbols` (comma-separated) defaults to the same `default_watchlist()`
    the screener uses (crypto + biquote-backed forex/métal/index/énergie --
    no Twelve Data equities, to protect its scarce per-minute budget on a
    request that fans out to N upstream calls); pass explicit symbols
    (equities included) to override. `method=log_returns` (default) is the
    correlation of bar-to-bar log returns, the standard choice for
    non-stationary price series; `method=price` correlates raw closes
    instead, mostly useful for sanity-checking against the return-based
    number.
    """
    symbol_list = (
        [s.strip().upper() for s in symbols.split(",") if s.strip()]
        if symbols
        else list(default_watchlist())
    )
    if not symbol_list:
        raise HTTPException(
            status_code=422,
            detail="no_symbols: provide at least one symbol or omit `symbols` for the default watchlist",
        )
    if len(symbol_list) > _MAX_CORRELATION_SYMBOLS:
        raise HTTPException(
            status_code=422,
            detail=f"too_many_symbols: max {_MAX_CORRELATION_SYMBOLS} symbols per request",
        )

    try:
        result = compute_correlation_matrix(
            symbol_list, timeframe=timeframe, limit=limit, method=method
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return {
        "timeframe": result.timeframe,
        "method": result.method,
        "symbols": result.symbols,
        "sample_size": result.sample_size,
        "matrix": result.matrix,
        "skipped": [{"symbol": s.symbol, "reason": s.reason} for s in result.skipped],
    }

