"""HTTP surface for the engine, mounted under `settings.engine_api_prefix`
(default `/api/engine`). Response shape for a single decision matches the
mission brief's example JSON (symbol/timeframe/decision/confidence/
ichimoku_score/rvol/reasons/risks/invalidation/timestamp) plus a few extra
fields (direction, probability, price, per-agent detail) useful for a UI.
"""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from app.agent_channel.registry import TOOLS, dispatch_command, list_tool_specs
from app.api.serializers import backtest_dict, detail_dict, metrics_dict, summary_dict
from app.backtest import experiments
from app.config import settings
from app.correlation.engine import compute_correlation_matrix
from app.db.session import SessionLocal
from app.indicators.atr import AtrParams
from app.indicators.rvol import RvolParams
from app.market_data import twelve_data
from app.paper import engine as paper_engine
from app.paper.performance import compute_performance
from app.screener.cache import screener_cache
from app.screener.persistence import persist_scan
from app.screener.service import scan_symbol, scan_watchlist
from app.universe.catalog import UNIVERSE, default_watchlist
from app.universe.types import AssetClass

router = APIRouter(prefix=settings.engine_api_prefix, tags=["engine"])


def _rvol_params_override(
    low: float | None,
    significant: float | None,
    strong: float | None,
    anomaly: float | None,
) -> RvolParams:
    """CDC V1 "Seuils RVOL/ATR configurables Settings": only the anomaly
    buckets are exposed to the caller, never `primary_window`/
    `percentile_lookback` -- those are indicator internals, not a product
    threshold. `None` means "leave this one at its default"."""
    d = RvolParams()
    low = d.low_threshold if low is None else low
    significant = d.significant_threshold if significant is None else significant
    strong = d.strong_threshold if strong is None else strong
    anomaly = d.anomaly_threshold if anomaly is None else anomaly
    if not (0 <= low < significant < strong < anomaly):
        raise HTTPException(
            status_code=422,
            detail="invalid_rvol_thresholds: expected 0 <= rvol_low < rvol_significant < rvol_strong < rvol_anomaly",
        )
    return RvolParams(
        low_threshold=low,
        significant_threshold=significant,
        strong_threshold=strong,
        anomaly_threshold=anomaly,
    )


def _atr_params_override(
    dead_percentile: float | None,
    extreme_percentile: float | None,
    stop_multiplier: float | None,
) -> AtrParams:
    d = AtrParams()
    dead_percentile = d.dead_percentile if dead_percentile is None else dead_percentile
    extreme_percentile = d.extreme_percentile if extreme_percentile is None else extreme_percentile
    stop_multiplier = d.stop_multiplier if stop_multiplier is None else stop_multiplier
    if not (0 <= dead_percentile < extreme_percentile <= 1):
        raise HTTPException(
            status_code=422,
            detail="invalid_atr_percentiles: expected 0 <= atr_dead_percentile < atr_extreme_percentile <= 1",
        )
    if stop_multiplier <= 0:
        raise HTTPException(status_code=422, detail="invalid_atr_stop_multiplier: must be > 0")
    return AtrParams(
        dead_percentile=dead_percentile,
        extreme_percentile=extreme_percentile,
        stop_multiplier=stop_multiplier,
    )


@router.get("/universe")
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


@router.get("/ohlcv/{symbol}")
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


@router.get("/screener")
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


@router.get("/decisions/{symbol}")
def get_decision(
    symbol: str,
    timeframe: str = "1h",
    limit: int = 300,
    persist: bool = True,
    include_candles: bool = False,
    rvol_low: float | None = None,
    rvol_significant: float | None = None,
    rvol_strong: float | None = None,
    rvol_anomaly: float | None = None,
    atr_dead_percentile: float | None = None,
    atr_extreme_percentile: float | None = None,
    atr_stop_multiplier: float | None = None,
    x_twelve_data_key: str | None = Header(default=None, alias="X-Twelve-Data-Key"),
) -> dict:
    twelve_data.set_api_key_override(x_twelve_data_key)
    rvol_params = _rvol_params_override(rvol_low, rvol_significant, rvol_strong, rvol_anomaly)
    atr_params = _atr_params_override(atr_dead_percentile, atr_extreme_percentile, atr_stop_multiplier)
    try:
        row = scan_symbol(
            symbol.upper(), timeframe=timeframe, limit=limit, rvol_params=rvol_params, atr_params=atr_params
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    if persist:
        session = SessionLocal()
        try:
            persist_scan(session, row)
        finally:
            session.close()

    payload = detail_dict(row)
    if include_candles:
        payload["candles"] = [
            {
                "time": c.time,
                "open": c.open,
                "high": c.high,
                "low": c.low,
                "close": c.close,
                "volume": c.volume,
            }
            for c in row.candles
        ]
        payload["provider"] = row.exchange
    return payload


_MAX_BATCH_ITEMS = 60
_BATCH_CONCURRENCY = 6


class BatchDecisionItem(BaseModel):
    symbol: str
    timeframe: str = "1h"


class BatchDecisionsRequest(BaseModel):
    items: list[BatchDecisionItem] = Field(default_factory=list)
    persist: bool = True


def _scan_for_batch(item: BatchDecisionItem, *, persist: bool) -> dict:
    symbol = item.symbol.upper()
    try:
        row = scan_symbol(symbol, timeframe=item.timeframe)
    except ValueError as exc:
        return {"symbol": symbol, "timeframe": item.timeframe, "ok": False, "error": str(exc)}

    if persist:
        session = SessionLocal()
        try:
            persist_scan(session, row)
        finally:
            session.close()

    return {"ok": True, **detail_dict(row)}


@router.post("/decisions/batch")
def get_decisions_batch(payload: BatchDecisionsRequest) -> dict:
    """Optional batch variant of `GET /decisions/{symbol}` (CDC V2 backlog,
    docs/HANDOFF-CURSOR-SESSION-2026-09-16-SOIR.md §3: "batch decisions
    optionnel") -- lets a caller that needs many symbols at once (the server
    Journal watch job, app/server/src/notifications/watch.ts, currently
    re-fetches its confirmed symbols one HTTP call at a time) fetch them
    concurrently in a single request instead of N sequential ones. Same
    response shape per item as the single-symbol endpoint's `detail_dict`
    (so `pipelineFingerprint()` on the server side needs no changes), plus
    `ok`/`error` so one bad symbol never fails the whole batch. Not a
    replacement for `/decisions/{symbol}` -- no RVOL/ATR threshold
    overrides, no `include_candles`, capped at `_MAX_BATCH_ITEMS` items so
    one request can't fan out into an unbounded number of upstream market
    data calls.
    """
    if not payload.items:
        return {"results": []}
    if len(payload.items) > _MAX_BATCH_ITEMS:
        raise HTTPException(
            status_code=422,
            detail=f"batch_too_large: max {_MAX_BATCH_ITEMS} items per request",
        )

    results: list[dict | None] = [None] * len(payload.items)
    with ThreadPoolExecutor(max_workers=_BATCH_CONCURRENCY) as pool:
        futures = {
            pool.submit(_scan_for_batch, item, persist=payload.persist): index
            for index, item in enumerate(payload.items)
        }
        for future in as_completed(futures):
            index = futures[future]
            item = payload.items[index]
            try:
                results[index] = future.result()
            except Exception as exc:  # noqa: BLE001 -- one symbol's failure must not sink the batch
                results[index] = {
                    "symbol": item.symbol.upper(),
                    "timeframe": item.timeframe,
                    "ok": False,
                    "error": str(exc),
                }

    return {"results": results}


@router.get("/backtest/{symbol}")
def get_backtest(
    symbol: str,
    timeframe: str = "1h",
    limit: int = 1000,
    rvol_low: float | None = None,
    rvol_significant: float | None = None,
    rvol_strong: float | None = None,
    rvol_anomaly: float | None = None,
    atr_dead_percentile: float | None = None,
    atr_extreme_percentile: float | None = None,
    atr_stop_multiplier: float | None = None,
    x_twelve_data_key: str | None = Header(default=None, alias="X-Twelve-Data-Key"),
) -> dict:
    """Compares ICHIMOKU_ONLY / ICHIMOKU_RVOL / ICHIMOKU_RVOL_ENTRY_GATE /
    PIPELINE over the same historical window -- see
    app/backtest/experiments.py for what each variant actually does. Not
    persisted (unlike /decisions): a backtest run isn't a live decision, and
    re-running it is cheap and deterministic given the same historical
    data. RVOL/ATR threshold overrides let a Settings tweak be validated by
    backtest before it's trusted live."""
    twelve_data.set_api_key_override(x_twelve_data_key)
    rvol_params = _rvol_params_override(rvol_low, rvol_significant, rvol_strong, rvol_anomaly)
    atr_params = _atr_params_override(atr_dead_percentile, atr_extreme_percentile, atr_stop_multiplier)
    try:
        results = experiments.compare(
            symbol.upper(), timeframe=timeframe, limit=limit, rvol_params=rvol_params, atr_params=atr_params
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return {
        "symbol": symbol.upper(),
        "timeframe": timeframe,
        "experiments": {
            name: {
                "metrics": metrics_dict(exp.metrics),
                "backtest": backtest_dict(exp.backtest),
            }
            for name, exp in results.items()
        },
    }


_MAX_CORRELATION_SYMBOLS = 40


@router.get("/correlations")
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


def _paper_position_dict(p) -> dict:
    return {
        "id": p.id,
        "symbol": p.symbol,
        "timeframe": p.timeframe,
        "source": p.source,
        "user_id": p.user_id,
        "direction": p.direction,
        "status": p.status,
        "entry_time": p.entry_time.isoformat(),
        "entry_price": p.entry_price,
        "entry_decision": p.entry_decision,
        "exit_time": p.exit_time.isoformat() if p.exit_time else None,
        "exit_price": p.exit_price,
        "exit_reason": p.exit_reason,
        "pnl_pct": p.pnl_pct,
    }


@router.get("/paper/positions")
def list_paper_positions(
    source: str | None = None, user_id: str | None = None, status: str | None = None
) -> dict:
    """Virtual positions only (CDC V2 "Paper trading") -- app/paper/engine.py
    owns open/close rules, this just lists them. `source=auto_watchlist`
    (no `user_id`) is the background screener's own shadow portfolio;
    `source=user_confirmed` + `user_id` is one user's confirmed picks."""
    session = SessionLocal()
    try:
        positions = paper_engine.list_positions(session, source=source, user_id=user_id, status=status)
        return {"positions": [_paper_position_dict(p) for p in positions]}
    finally:
        session.close()


@router.get("/paper/performance")
def get_paper_performance(source: str | None = None, user_id: str | None = None) -> dict:
    """Trade-level performance (CDC V2 "Performance/calibration") over
    whatever (source, user_id) scope is asked for -- app/paper/performance.py
    for exactly what is and isn't computed and why (no Sharpe/Sortino/
    drawdown here, those need a continuous equity curve this data doesn't
    have yet)."""
    session = SessionLocal()
    try:
        positions = paper_engine.list_positions(session, source=source, user_id=user_id)
        perf = compute_performance(positions)
    finally:
        session.close()

    return {
        "num_closed_trades": perf.num_closed_trades,
        "num_open_positions": perf.num_open_positions,
        "total_return": perf.total_return,
        "win_rate": perf.win_rate,
        "profit_factor": perf.profit_factor if perf.profit_factor != float("inf") else None,
        "expectancy": perf.expectancy,
        "avg_holding_hours": perf.avg_holding_hours,
        "best_trade_pct": perf.best_trade_pct,
        "worst_trade_pct": perf.worst_trade_pct,
    }


@router.post("/paper/positions")
def open_paper_position(
    symbol: str,
    user_id: str,
    timeframe: str = "1h",
    rvol_low: float | None = None,
    rvol_significant: float | None = None,
    rvol_strong: float | None = None,
    rvol_anomaly: float | None = None,
    atr_dead_percentile: float | None = None,
    atr_extreme_percentile: float | None = None,
    atr_stop_multiplier: float | None = None,
) -> dict:
    """Called by the server when a user hits "Confirmer" in the Journal --
    opens a virtual `user_confirmed` position at the current live
    price/decision, unless one is already open for this (symbol, timeframe,
    user_id) (idempotent) or the live decision isn't actionable right now.

    Same 7 optional RVOL/ATR threshold overrides as `/decisions/{symbol}` and
    `/screener` (previously missing here -- feature parity gap, not a new
    concept): lets a caller open a position under a deliberately-labeled
    demo/calibration threshold set instead of the engine defaults, using the
    exact same real market data and pipeline logic either way."""
    rvol_params = _rvol_params_override(rvol_low, rvol_significant, rvol_strong, rvol_anomaly)
    atr_params = _atr_params_override(atr_dead_percentile, atr_extreme_percentile, atr_stop_multiplier)
    try:
        row = scan_symbol(
            symbol.upper(), timeframe=timeframe, rvol_params=rvol_params, atr_params=atr_params
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    session = SessionLocal()
    try:
        position = paper_engine.open_user_confirmed(
            session, symbol=row.symbol, timeframe=timeframe, user_id=user_id,
            price=row.price, pipeline=row.pipeline,
        )
        if position is None:
            raise HTTPException(
                status_code=422,
                detail="not_actionable: pipeline.decision is WATCH/NO_TRADE, nothing to open",
            )
        # Serialize while the session is still open: `commit()` inside
        # open_user_confirmed() expires the instance's attributes, and
        # reading them after session.close() raises DetachedInstanceError.
        return _paper_position_dict(position)
    finally:
        session.close()


@router.post("/paper/positions/{position_id}/close")
def close_paper_position(position_id: str) -> dict:
    """Manual close at the current live price for that position's own
    symbol/timeframe -- e.g. wired to archiving a Journal entry."""
    session = SessionLocal()
    try:
        existing = paper_engine.get_position(session, position_id)
        if existing is None:
            raise HTTPException(status_code=404, detail="position_not_found")
        if existing.status != "OPEN":
            raise HTTPException(status_code=409, detail="position_already_closed")
        symbol, timeframe = existing.symbol, existing.timeframe
    finally:
        session.close()

    try:
        row = scan_symbol(symbol, timeframe=timeframe)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    session = SessionLocal()
    try:
        closed = paper_engine.close_manually(session, position_id, price=row.price)
        if closed is None:
            raise HTTPException(status_code=409, detail="position_already_closed")
        return _paper_position_dict(closed)  # while the session is still open, see open_paper_position
    finally:
        session.close()


_AGENT_CHANNEL_VERSION = "engine_agent_v1"
_MAX_AGENT_BATCH_ITEMS = 20
_AGENT_BATCH_CONCURRENCY = 6


@router.get("/agent/tools")
def get_agent_tools() -> dict:
    """Allowlist introspection -- same content `list_tools` (the command)
    returns, as a plain GET for a client that just wants to enumerate
    capabilities without a POST body."""
    return {"tools": list_tool_specs()}


@router.get("/agent/capabilities")
def get_agent_capabilities() -> dict:
    """Stub-level capabilities descriptor (per brief: "stub OK"). No WRITE
    tier in this pass -- paper trading stays reachable only through
    `POST /paper/positions` directly (app/paper/engine.py), never through
    this command channel, until a WRITE allowlist is explicitly asked for."""
    return {
        "version": _AGENT_CHANNEL_VERSION,
        "read_only": True,
        "write_tier_enabled": False,
        "max_batch_items": _MAX_AGENT_BATCH_ITEMS,
        "commands": sorted(TOOLS.keys()),
    }


class AgentCommandRequest(BaseModel):
    cmd: str
    args: dict = Field(default_factory=dict)


@router.post("/agent/command")
def post_agent_command(payload: AgentCommandRequest) -> dict:
    """Single-command entry point: `{cmd, args}` -> `{ok, cmd, data|error}`.
    Never raises for a client-caused failure (unknown command, bad args) --
    see app/agent_channel/registry.py::dispatch_command."""
    return dispatch_command(payload.cmd, payload.args)


class AgentBatchItem(BaseModel):
    cmd: str
    args: dict = Field(default_factory=dict)


class AgentBatchRequest(BaseModel):
    commands: list[AgentBatchItem] = Field(default_factory=list)


@router.post("/agent/batch")
def post_agent_batch(payload: AgentBatchRequest) -> dict:
    """Concurrent batch of up to `_MAX_AGENT_BATCH_ITEMS` commands, results
    returned in the SAME ORDER as the request (order-stable) regardless of
    which finishes first -- same pattern as `POST /decisions/batch`."""
    if not payload.commands:
        return {"results": []}
    if len(payload.commands) > _MAX_AGENT_BATCH_ITEMS:
        raise HTTPException(
            status_code=422,
            detail=f"batch_too_large: max {_MAX_AGENT_BATCH_ITEMS} commands per request",
        )

    results: list[dict | None] = [None] * len(payload.commands)
    with ThreadPoolExecutor(max_workers=_AGENT_BATCH_CONCURRENCY) as pool:
        futures = {
            pool.submit(dispatch_command, item.cmd, item.args): index
            for index, item in enumerate(payload.commands)
        }
        for future in as_completed(futures):
            index = futures[future]
            item = payload.commands[index]
            try:
                results[index] = future.result()
            except Exception as exc:  # noqa: BLE001 -- one command's crash must not sink the batch
                results[index] = {"ok": False, "cmd": item.cmd, "error": f"internal_error: {exc}"}

    return {"results": results}
