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
from app.backtest.evidence import compute_evidence_summary
from app.config import settings
from app.context.calendar import fetch_calendar_events
from app.context.news import fetch_news
from app.correlation.engine import compute_correlation_matrix
from app.db.session import SessionLocal
from app.indicators.atr import AtrParams, compute_atr
from app.indicators.cmf import compute_cmf
from app.indicators.obv import compute_obv
from app.indicators.rsi import compute_rsi
from app.indicators.rvol import RvolParams
from app.market_data import twelve_data
from app.paper import engine as paper_engine
from app.paper.performance import compute_performance, compute_portfolio_performance
from app.paper.portfolio import (
    ensure_baseline_portfolio,
    ensure_portfolio,
    ensure_syncable_portfolios,
    get_portfolio_by_code,
    list_portfolios,
)
from app.paper.strategy_profiles import ALL_PROFILES, BASELINE_CODE
from app.screener.cache import screener_cache
from app.screener.persistence import persist_scan
from app.screener.service import scan_symbol, scan_watchlist
from app.strategy_lab.ablation import ablation_dict, run_ablation
from app.strategy_lab.catalog import get_builtin_ruleset, list_builtin_rulesets
from app.strategy_lab.event_study import event_study_dict, run_event_study
from app.strategy_lab.optimization import (
    optimize_dict,
    run_optimize,
    run_walk_forward_opt,
    walk_forward_opt_dict,
)
from app.strategy_lab.perf_db import (
    compare_rulesets,
    experiment_dict,
    get_experiment,
    list_experiments,
    persist_study_result,
)
from app.strategy_lab.regime_slices import regime_slices_dict, run_regime_slices
from app.strategy_lab.ruleset import CONDITION_SCHEMA, parse_ruleset
from app.strategy_lab.run_ruleset import ruleset_study_dict, run_ruleset_event_study
from app.strategy_lab.walk_forward import run_walk_forward, walk_forward_dict
from app.shadow.broker import list_shadows, shadow_stats, shadow_to_dict
from app.structure.params import StructureEngineParams
from app.structure.service import detect_market_structure
from app.structure.types import PriceZone, TrendlineSegment
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


def _zone_dict(z: PriceZone) -> dict:
    return {
        "side": z.side.value,
        "low": z.low,
        "high": z.high,
        "mid": z.mid,
        "score": z.score,
        "touch_count": z.touch_count,
        "sources": [s.value for s in z.sources],
        "atr_width": z.atr_width,
    }


def _line_dict(line: TrendlineSegment, series: list | None = None) -> dict:
    out = {
        "side": line.side.value,
        "slope": line.slope,
        "intercept": line.intercept,
        "start_bar": line.start_bar,
        "end_bar": line.end_bar,
        "touch_count": line.touch_count,
        "score": line.score,
        "source": line.source.value,
        "pivot_bars": list(line.pivot_bars),
    }
    # Bar indices are relative to the detector's windowed series; the chart
    # needs absolute time/price to draw the segment. `series` is that window.
    if series and 0 <= line.start_bar < len(series) and 0 <= line.end_bar < len(series):
        out["start_time"] = series[line.start_bar].time
        out["end_time"] = series[line.end_bar].time
        out["start_price"] = line.price_at(line.start_bar)
        out["end_price"] = line.price_at(line.end_bar)
    return out


@router.get("/structure/{symbol}")
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


@router.get("/context/news")
def get_context_news(limit: int = 20, sources: str | None = None) -> dict:
    """Read-only crypto news headlines (CDC "adapters context", V3, opt-in)
    -- free/keyless RSS, never wired into the decision pipeline (see
    app/context/news.py). `sources` (comma-separated) restricts to a subset
    of `news.FEEDS`; omit for all of them. One feed failing never empties
    the others -- worst case this returns `[]`, never a 502."""
    source_list = [s.strip() for s in sources.split(",") if s.strip()] if sources else None
    items = fetch_news(limit=limit, sources=source_list)
    return {
        "items": [
            {"title": i.title, "url": i.url, "source": i.source, "published_at": i.published_at}
            for i in items
        ]
    }


@router.get("/context/calendar")
def get_context_calendar(limit: int | None = None) -> dict:
    """Read-only macro economic calendar, this week (CDC "adapters context",
    V3, opt-in) -- free/keyless community feed, never wired into the
    decision pipeline (see app/context/calendar.py). Degrades to an empty
    list on any upstream failure, never a 502."""
    events = fetch_calendar_events(limit=limit)
    return {
        "events": [
            {
                "title": e.title, "country": e.country, "date": e.date,
                "impact": e.impact, "forecast": e.forecast, "previous": e.previous,
            }
            for e in events
        ]
    }


def _paper_position_dict(p) -> dict:
    return {
        "id": p.id,
        "portfolio_id": p.portfolio_id,
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
        "qty": p.qty,
        "notional": p.notional,
        "stop_price": p.stop_price,
        "take_profit_price": p.take_profit_price,
        "risk_pct": p.risk_pct,
        "risk_amount": p.risk_amount,
        "entry_fee": getattr(p, "entry_fee", None),
        "exit_fee": getattr(p, "exit_fee", None),
        "realized_pnl": p.realized_pnl,
        "mfe_pct": p.mfe_pct,
        "mae_pct": p.mae_pct,
        "decision_id": getattr(p, "decision_id", None),
        "evidence_id": getattr(p, "evidence_id", None),
        "entry_signal": getattr(p, "entry_signal", None),
    }


def _paper_perf_dict(perf) -> dict:
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
        "initial_cash": getattr(perf, "initial_cash", None),
        "cash": getattr(perf, "cash", None),
        "equity": getattr(perf, "equity", None),
        "realized_pnl": getattr(perf, "realized_pnl", None),
        "unrealized_pnl": getattr(perf, "unrealized_pnl", None),
        "max_drawdown": getattr(perf, "max_drawdown", None),
        "expectancy_eur": getattr(perf, "expectancy_eur", None),
        "valuation_mode": getattr(perf, "valuation_mode", None),
    }


def _portfolio_dict(p) -> dict:
    return {
        "id": p.id,
        "code": p.code,
        "label": p.label,
        "currency": p.currency,
        "valuation_mode": p.valuation_mode,
        "initial_cash": p.initial_cash,
        "cash": p.cash,
        "realized_pnl": p.realized_pnl,
        "is_active": p.is_active,
        "started_at": p.started_at.isoformat(),
        "strategy_profile": p.strategy_profile,
    }


@router.get("/context/{symbol}")
def get_context_indicators(
    symbol: str,
    timeframe: str = "1h",
    limit: int = 300,
    x_twelve_data_key: str | None = Header(default=None, alias="X-Twelve-Data-Key"),
) -> dict:
    """Phase 3 context snapshot: RSI + CMF + OBV + ATR regime (analysis only)."""
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

    rsi = compute_rsi(candles)[-1]
    cmf = compute_cmf(candles)[-1]
    obv = compute_obv(candles)[-1]
    atr = compute_atr(candles)[-1]
    return {
        "symbol": symbol.upper(),
        "timeframe": timeframe,
        "provider": provider.id,
        "provider_symbol": provider_symbol,
        "last_close": candles[-1].close,
        "rsi": {"value": rsi.rsi, "bias": rsi.bias.value},
        "cmf": {"value": cmf.cmf, "bias": cmf.bias.value},
        "obv": {"value": obv.obv, "bias": obv.bias.value, "slope": obv.slope},
        "atr": {
            "value": atr.atr,
            "regime": atr.regime.value,
            "suggested_stop_distance": atr.suggested_stop_distance,
        },
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

    # Paper order intent (suggest before act) — never a live order.
    session = SessionLocal()
    try:
        from app.paper.intent import propose_order_intent

        payload["order_intent"] = propose_order_intent(session, row).to_dict()
    except Exception:
        payload["order_intent"] = None
    finally:
        session.close()
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


@router.get("/backtest/evidence")
def get_backtest_evidence() -> dict:
    """Rollup for the Overview "Preuve edge (C1)" tile -- how much automated
    backtest evidence has been collected (app/backtest/evidence.py's
    scheduled job) and how often PIPELINE's Sharpe beat plain Ichimoku in
    the most recent cycle. Purely descriptive, never a verdict: Option C
    stays a reviewed call, this just makes the raw material visible.
    Declared before `/backtest/{symbol}` so `evidence` is never parsed as a
    symbol path param."""
    session = SessionLocal()
    try:
        return compute_evidence_summary(session)
    finally:
        session.close()


@router.get("/event-study/{symbol}")
def get_event_study(
    symbol: str,
    timeframe: str = "1h",
    limit: int = 1000,
    variant: str = experiments.PIPELINE,
    horizons: str = "1,3,5,10",
    r_multiple: float = 1.0,
    include_events: bool = False,
) -> dict:
    """Strategy Lab Phase 1 — Event Study.

    For each entry signal of the named backtest variant, measure forward
    ATR-normalized returns at +N candles, MFE/MAE, and % hitting +R before -R.
    No capital, fees, or sizing. Complements `/backtest/{symbol}` (full
    simulator) without replacing it.
    """
    try:
        horizon_list = tuple(
            int(x.strip()) for x in horizons.split(",") if x.strip()
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=422, detail="horizons must be comma-separated integers"
        ) from exc
    if not horizon_list or any(h < 1 for h in horizon_list):
        raise HTTPException(status_code=422, detail="horizons must be positive integers")
    if r_multiple <= 0:
        raise HTTPException(status_code=422, detail="r_multiple must be > 0")
    if limit < 50 or limit > 5000:
        raise HTTPException(status_code=422, detail="limit must be between 50 and 5000")

    try:
        result = run_event_study(
            symbol.upper(),
            timeframe=timeframe,
            limit=limit,
            variant=variant,
            horizons=horizon_list,
            r_multiple=r_multiple,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return event_study_dict(result, include_events=include_events)


@router.get("/rulesets")
def get_rulesets() -> dict:
    """Strategy Lab Phase 2 — list built-in declarative rulesets + condition schema."""
    return {
        "rulesets": [r.to_dict() for r in list_builtin_rulesets()],
        "condition_keys": sorted(CONDITION_SCHEMA.keys()),
    }


class RulesetStudyBody(BaseModel):
    symbol: str
    timeframe: str = "1h"
    limit: int = 1000
    horizons: str = "1,3,5,10"
    include_events: bool = False
    with_backtest: bool = True
    persist: bool = False
    """If true, save results to strategy_lab_experiments (Performance DB)."""
    ruleset_id: str | None = None
    """Built-in id; ignored if `ruleset` body is provided."""
    ruleset: dict | None = None
    """Inline ruleset JSON (takes precedence over ruleset_id)."""


@router.post("/ruleset/event-study")
def post_ruleset_event_study(body: RulesetStudyBody) -> dict:
    """Strategy Lab Phase 2 — evaluate a ruleset then run Event Study on rising-edge hits."""
    try:
        horizon_list = tuple(
            int(x.strip()) for x in body.horizons.split(",") if x.strip()
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=422, detail="horizons must be comma-separated integers"
        ) from exc
    if not horizon_list or any(h < 1 for h in horizon_list):
        raise HTTPException(status_code=422, detail="horizons must be positive integers")
    if body.limit < 50 or body.limit > 5000:
        raise HTTPException(status_code=422, detail="limit must be between 50 and 5000")

    try:
        if body.ruleset is not None:
            ruleset = parse_ruleset(body.ruleset)
        elif body.ruleset_id:
            ruleset = get_builtin_ruleset(body.ruleset_id)
        else:
            raise HTTPException(
                status_code=422, detail="provide ruleset_id or ruleset object"
            )
        result = run_ruleset_event_study(
            ruleset,
            body.symbol.upper(),
            timeframe=body.timeframe,
            limit=body.limit,
            horizons=horizon_list,
            with_backtest=body.with_backtest,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    payload = ruleset_study_dict(result, include_events=body.include_events)
    if body.persist:
        try:
            saved = persist_study_result(
                result,
                parameters={
                    "limit": body.limit,
                    "horizons": list(horizon_list),
                    "with_backtest": body.with_backtest,
                },
            )
            payload["experiment"] = saved
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"persist_failed: {exc}") from exc
    return payload


@router.get("/ruleset/{ruleset_id}/event-study")
def get_ruleset_event_study(
    ruleset_id: str,
    symbol: str,
    timeframe: str = "1h",
    limit: int = 1000,
    horizons: str = "1,3,5,10",
    include_events: bool = False,
    with_backtest: bool = True,
    persist: bool = False,
) -> dict:
    """Run a built-in ruleset Event Study (+ ATR backtest by default)."""
    try:
        horizon_list = tuple(
            int(x.strip()) for x in horizons.split(",") if x.strip()
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=422, detail="horizons must be comma-separated integers"
        ) from exc
    if not horizon_list or any(h < 1 for h in horizon_list):
        raise HTTPException(status_code=422, detail="horizons must be positive integers")
    if limit < 50 or limit > 5000:
        raise HTTPException(status_code=422, detail="limit must be between 50 and 5000")

    try:
        ruleset = get_builtin_ruleset(ruleset_id)
        result = run_ruleset_event_study(
            ruleset,
            symbol.upper(),
            timeframe=timeframe,
            limit=limit,
            horizons=horizon_list,
            with_backtest=with_backtest,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    payload = ruleset_study_dict(result, include_events=include_events)
    if persist:
        try:
            saved = persist_study_result(
                result,
                parameters={
                    "limit": limit,
                    "horizons": list(horizon_list),
                    "with_backtest": with_backtest,
                },
            )
            payload["experiment"] = saved
        except Exception as exc:
            raise HTTPException(status_code=500, detail=f"persist_failed: {exc}") from exc
    return payload


@router.get("/strategy-lab/experiments")
def get_strategy_lab_experiments(
    symbol: str | None = None,
    timeframe: str | None = None,
    ruleset_id: str | None = None,
    market_regime: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> dict:
    """Performance DB — list persisted Strategy Lab experiments."""
    session = SessionLocal()
    try:
        rows = list_experiments(
            session,
            symbol=symbol,
            timeframe=timeframe,
            ruleset_id=ruleset_id,
            market_regime=market_regime,
            limit=limit,
            offset=offset,
        )
        return {
            "experiments": [experiment_dict(r) for r in rows],
            "count": len(rows),
        }
    finally:
        session.close()


@router.get("/strategy-lab/experiments/{experiment_id}")
def get_strategy_lab_experiment(experiment_id: str) -> dict:
    session = SessionLocal()
    try:
        row = get_experiment(session, experiment_id)
        if row is None:
            raise HTTPException(status_code=404, detail="experiment_not_found")
        return experiment_dict(row)
    finally:
        session.close()


@router.get("/strategy-lab/compare")
def get_strategy_lab_compare(
    symbol: str,
    timeframe: str = "1h",
    ruleset_ids: str = "",
    market_regime: str = "GLOBAL",
) -> dict:
    """Latest saved run per ruleset_id for symbol/timeframe (ablation helper)."""
    ids = [x.strip() for x in ruleset_ids.split(",") if x.strip()]
    if not ids:
        raise HTTPException(status_code=422, detail="ruleset_ids required (comma-separated)")
    session = SessionLocal()
    try:
        rows = compare_rulesets(
            session,
            symbol=symbol.upper(),
            timeframe=timeframe,
            ruleset_ids=ids,
            market_regime=market_regime,
        )
        return {
            "symbol": symbol.upper(),
            "timeframe": timeframe,
            "market_regime": market_regime,
            "experiments": [experiment_dict(r) for r in rows],
        }
    finally:
        session.close()


class AblationBody(BaseModel):
    symbol: str
    timeframe: str = "1h"
    limit: int = 1000
    mode: str = "cumulative"
    """cumulative | leave_one_out"""
    direction: str = "LONG"
    stop_atr: float = 1.0
    target_atr: float = 2.0
    persist: bool = False
    layers: list[dict] | None = None
    """Optional [{label, conditions}] — default A→E ladder if omitted (cumulative)."""


@router.post("/strategy-lab/ablation")
def post_strategy_lab_ablation(body: AblationBody) -> dict:
    """Strategy Lab Phase 5 — run ablation matrix on one shared OHLCV window."""
    if body.limit < 50 or body.limit > 5000:
        raise HTTPException(status_code=422, detail="limit must be between 50 and 5000")
    if body.stop_atr <= 0 or body.target_atr <= 0:
        raise HTTPException(status_code=422, detail="stop_atr/target_atr must be > 0")
    try:
        result = run_ablation(
            body.symbol.upper(),
            timeframe=body.timeframe,
            limit=body.limit,
            mode=body.mode,
            layers=body.layers,
            direction=body.direction,
            stop_atr=body.stop_atr,
            target_atr=body.target_atr,
            persist=body.persist,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return ablation_dict(result)


@router.get("/strategy-lab/ablation")
def get_strategy_lab_ablation(
    symbol: str,
    timeframe: str = "1h",
    limit: int = 1000,
    mode: str = "cumulative",
    direction: str = "LONG",
    persist: bool = False,
) -> dict:
    """Convenience GET — default A→E cumulative ladder (Ichimoku→RVOL→BOS→ATR→CMF)."""
    if limit < 50 or limit > 5000:
        raise HTTPException(status_code=422, detail="limit must be between 50 and 5000")
    try:
        result = run_ablation(
            symbol.upper(),
            timeframe=timeframe,
            limit=limit,
            mode=mode,
            direction=direction,
            persist=persist,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return ablation_dict(result)


class RegimeSlicesBody(BaseModel):
    symbol: str
    timeframe: str = "1h"
    limit: int = 1000
    persist: bool = False
    ruleset_id: str | None = "IV_ICHIMOKU_RVOL_LONG_001"
    ruleset: dict | None = None


@router.post("/strategy-lab/regime-slices")
def post_strategy_lab_regime_slices(body: RegimeSlicesBody) -> dict:
    """Strategy Lab Phase 6 — segment ruleset performance by market regime."""
    if body.limit < 50 or body.limit > 5000:
        raise HTTPException(status_code=422, detail="limit must be between 50 and 5000")
    try:
        report = run_regime_slices(
            body.symbol.upper(),
            timeframe=body.timeframe,
            limit=body.limit,
            ruleset_id=body.ruleset_id,
            ruleset=body.ruleset,
            persist=body.persist,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return regime_slices_dict(report)


@router.get("/strategy-lab/regime-slices")
def get_strategy_lab_regime_slices(
    symbol: str,
    timeframe: str = "1h",
    limit: int = 1000,
    ruleset_id: str = "IV_ICHIMOKU_RVOL_LONG_001",
    persist: bool = False,
) -> dict:
    if limit < 50 or limit > 5000:
        raise HTTPException(status_code=422, detail="limit must be between 50 and 5000")
    try:
        report = run_regime_slices(
            symbol.upper(),
            timeframe=timeframe,
            limit=limit,
            ruleset_id=ruleset_id,
            persist=persist,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return regime_slices_dict(report)


class WalkForwardBody(BaseModel):
    symbol: str
    timeframe: str = "1h"
    limit: int = 1000
    mode: str = "rolling"
    train_bars: int = 400
    test_bars: int = 100
    step_bars: int | None = None
    warmup_bars: int = 52
    include_train: bool = True
    persist: bool = False
    ruleset_id: str | None = "IV_ICHIMOKU_RVOL_LONG_001"
    ruleset: dict | None = None


@router.post("/strategy-lab/walk-forward")
def post_strategy_lab_walk_forward(body: WalkForwardBody) -> dict:
    """Strategy Lab Phase 7 — walk-forward IS/OOS on a fixed ruleset (no optimizer)."""
    if body.limit < 100 or body.limit > 5000:
        raise HTTPException(status_code=422, detail="limit must be between 100 and 5000")
    try:
        report = run_walk_forward(
            body.symbol.upper(),
            timeframe=body.timeframe,
            limit=body.limit,
            ruleset_id=body.ruleset_id,
            ruleset=body.ruleset,
            mode=body.mode,
            train_bars=body.train_bars,
            test_bars=body.test_bars,
            step_bars=body.step_bars,
            warmup_bars=body.warmup_bars,
            include_train=body.include_train,
            persist=body.persist,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return walk_forward_dict(report)


@router.get("/strategy-lab/walk-forward")
def get_strategy_lab_walk_forward(
    symbol: str,
    timeframe: str = "1h",
    limit: int = 1000,
    mode: str = "rolling",
    train_bars: int = 400,
    test_bars: int = 100,
    step_bars: int | None = None,
    warmup_bars: int = 52,
    include_train: bool = True,
    persist: bool = False,
    ruleset_id: str = "IV_ICHIMOKU_RVOL_LONG_001",
) -> dict:
    if limit < 100 or limit > 5000:
        raise HTTPException(status_code=422, detail="limit must be between 100 and 5000")
    try:
        report = run_walk_forward(
            symbol.upper(),
            timeframe=timeframe,
            limit=limit,
            ruleset_id=ruleset_id,
            mode=mode,
            train_bars=train_bars,
            test_bars=test_bars,
            step_bars=step_bars,
            warmup_bars=warmup_bars,
            include_train=include_train,
            persist=persist,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return walk_forward_dict(report)


class OptimizeBody(BaseModel):
    symbol: str
    timeframe: str = "1h"
    limit: int = 1000
    objective: str = "expectancy"
    min_trades: int = 5
    warmup_bars: int = 52
    persist_best: bool = False
    grid: dict[str, list] | None = None
    ruleset_id: str | None = "IV_ICHIMOKU_RVOL_LONG_001"
    ruleset: dict | None = None


@router.post("/strategy-lab/optimize")
def post_strategy_lab_optimize(body: OptimizeBody) -> dict:
    """Strategy Lab Phase 8 — single-window grid search (IS only; prefer WF-opt)."""
    if body.limit < 100 or body.limit > 5000:
        raise HTTPException(status_code=422, detail="limit must be between 100 and 5000")
    try:
        report = run_optimize(
            body.symbol.upper(),
            timeframe=body.timeframe,
            limit=body.limit,
            ruleset_id=body.ruleset_id,
            ruleset=body.ruleset,
            grid=body.grid,
            objective=body.objective,
            min_trades=body.min_trades,
            warmup_bars=body.warmup_bars,
            persist_best=body.persist_best,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return optimize_dict(report)


@router.get("/strategy-lab/optimize")
def get_strategy_lab_optimize(
    symbol: str,
    timeframe: str = "1h",
    limit: int = 1000,
    objective: str = "expectancy",
    min_trades: int = 5,
    warmup_bars: int = 52,
    persist_best: bool = False,
    ruleset_id: str = "IV_ICHIMOKU_RVOL_LONG_001",
) -> dict:
    if limit < 100 or limit > 5000:
        raise HTTPException(status_code=422, detail="limit must be between 100 and 5000")
    try:
        report = run_optimize(
            symbol.upper(),
            timeframe=timeframe,
            limit=limit,
            ruleset_id=ruleset_id,
            objective=objective,
            min_trades=min_trades,
            warmup_bars=warmup_bars,
            persist_best=persist_best,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return optimize_dict(report)


class WalkForwardOptBody(BaseModel):
    symbol: str
    timeframe: str = "1h"
    limit: int = 1000
    mode: str = "rolling"
    train_bars: int = 400
    test_bars: int = 100
    step_bars: int | None = None
    warmup_bars: int = 52
    objective: str = "expectancy"
    min_trades: int = 5
    persist: bool = False
    grid: dict[str, list] | None = None
    ruleset_id: str | None = "IV_ICHIMOKU_RVOL_LONG_001"
    ruleset: dict | None = None


@router.post("/strategy-lab/walk-forward-opt")
def post_strategy_lab_walk_forward_opt(body: WalkForwardOptBody) -> dict:
    """Strategy Lab Phase 8 — optimize on IS per fold, measure on OOS."""
    if body.limit < 100 or body.limit > 5000:
        raise HTTPException(status_code=422, detail="limit must be between 100 and 5000")
    try:
        report = run_walk_forward_opt(
            body.symbol.upper(),
            timeframe=body.timeframe,
            limit=body.limit,
            ruleset_id=body.ruleset_id,
            ruleset=body.ruleset,
            mode=body.mode,
            train_bars=body.train_bars,
            test_bars=body.test_bars,
            step_bars=body.step_bars,
            warmup_bars=body.warmup_bars,
            grid=body.grid,
            objective=body.objective,
            min_trades=body.min_trades,
            persist=body.persist,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return walk_forward_opt_dict(report)


@router.get("/strategy-lab/walk-forward-opt")
def get_strategy_lab_walk_forward_opt(
    symbol: str,
    timeframe: str = "1h",
    limit: int = 1000,
    mode: str = "rolling",
    train_bars: int = 400,
    test_bars: int = 100,
    step_bars: int | None = None,
    warmup_bars: int = 52,
    objective: str = "expectancy",
    min_trades: int = 5,
    persist: bool = False,
    ruleset_id: str = "IV_ICHIMOKU_RVOL_LONG_001",
) -> dict:
    if limit < 100 or limit > 5000:
        raise HTTPException(status_code=422, detail="limit must be between 100 and 5000")
    try:
        report = run_walk_forward_opt(
            symbol.upper(),
            timeframe=timeframe,
            limit=limit,
            ruleset_id=ruleset_id,
            mode=mode,
            train_bars=train_bars,
            test_bars=test_bars,
            step_bars=step_bars,
            warmup_bars=warmup_bars,
            objective=objective,
            min_trades=min_trades,
            persist=persist,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return walk_forward_opt_dict(report)


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
    """Trade-level + capital performance when baseline portfolio exists."""
    session = SessionLocal()
    try:
        positions = paper_engine.list_positions(session, source=source, user_id=user_id)
        portfolio = ensure_baseline_portfolio(session)
        session.commit()
        if source in (None, "auto_watchlist") and user_id is None:
            perf = compute_portfolio_performance(session, portfolio, positions)
        else:
            perf = compute_performance(positions)
        return _paper_perf_dict(perf)
    finally:
        session.close()


@router.get("/paper/portfolios")
def get_paper_portfolios() -> dict:
    session = SessionLocal()
    try:
        ensure_syncable_portfolios(session)
        session.commit()
        return {"portfolios": [_portfolio_dict(p) for p in list_portfolios(session)]}
    finally:
        session.close()


def _latest_marks() -> dict[str, tuple[float, float]]:
    """symbol -> (last screener price, computed_at epoch). Read-only cache peek."""
    marks: dict[str, tuple[float, float]] = {}
    for tf in ("1h", "4h", "15m", "1d"):
        entry = screener_cache.get(tf)
        if entry is None:
            continue
        for row in entry.rows:
            marks.setdefault(row.symbol, (row.price, entry.computed_at))
    return marks


@router.get("/paper/portfolios/{code}/overview")
def get_paper_portfolio_overview(code: str) -> dict:
    """Broker-style account view: cash / invested / unrealized P&L, open positions
    marked to the last screener price, and the equity curve. Read-only.
    """
    from datetime import datetime, timedelta, timezone

    from sqlalchemy import select

    from app.db.models import PaperEquitySnapshot

    session = SessionLocal()
    try:
        portfolio = get_portfolio_by_code(session, code)
        if portfolio is None:
            raise HTTPException(status_code=404, detail="portfolio_not_found")
        positions = paper_engine.list_positions(session, portfolio_id=portfolio.id)
        marks = _latest_marks()

        rows: list[dict] = []
        invested = 0.0
        unrealized = 0.0
        open_entry_fees = 0.0
        incomplete_open = 0
        for p in positions:
            d = _paper_position_dict(p)
            d["current_price"] = None
            d["unrealized_pnl"] = None
            d["unrealized_pct"] = None
            d["market_value"] = None
            d["valuation_status"] = None
            if p.status == "OPEN":
                invested += p.notional or 0.0
                open_entry_fees += float(p.entry_fee or 0.0)
                mark = marks.get(p.symbol)
                if p.qty is None:
                    d["valuation_status"] = "missing_qty"
                    incomplete_open += 1
                elif mark is None:
                    d["valuation_status"] = "missing_mark"
                    incomplete_open += 1
                elif p.notional is None:
                    d["valuation_status"] = "missing_notional"
                    incomplete_open += 1
                else:
                    d["valuation_status"] = "priced"
                if mark is not None and p.entry_price:
                    price = mark[0]
                    move = (price - p.entry_price) / p.entry_price
                    d["current_price"] = price
                    d["price_as_of"] = mark[1]
                    d["unrealized_pct"] = move if p.direction == "LONG" else -move
                    # € P&L only for capital-sized positions (legacy ones have no qty)
                    if p.qty:
                        gain = (
                            p.qty * (price - p.entry_price)
                            if p.direction == "LONG"
                            else p.qty * (p.entry_price - price)
                        )
                        d["unrealized_pnl"] = gain
                        d["market_value"] = p.qty * price
                        unrealized += gain
            rows.append(d)

        equity = portfolio.cash + invested + unrealized
        realized = float(portfolio.realized_pnl or 0.0)
        total_pnl = equity - portfolio.initial_cash
        snaps = (
            session.execute(
                select(PaperEquitySnapshot)
                .where(PaperEquitySnapshot.portfolio_id == portfolio.id)
                .order_by(PaperEquitySnapshot.timestamp.desc())
                .limit(500)
            )
            .scalars()
            .all()
        )
        curve = [
            {"t": s.timestamp.isoformat(), "equity": s.equity}
            for s in reversed(snaps)
        ]
        day_ago = datetime.now(timezone.utc) - timedelta(hours=24)
        ref = next(
            (
                s.equity
                for s in snaps
                if (s.timestamp if s.timestamp.tzinfo else s.timestamp.replace(tzinfo=timezone.utc))
                <= day_ago
            ),
            None,
        )
        open_n = sum(1 for r in rows if r["status"] == "OPEN")
        priced_n = sum(1 for r in rows if r["status"] == "OPEN" and r["valuation_status"] == "priced")
        return {
            "portfolio": _portfolio_dict(portfolio),
            "account": {
                "initial_cash": portfolio.initial_cash,
                "cash": portfolio.cash,
                "invested": invested,
                "unrealized_pnl": unrealized,
                "realized_pnl": realized,
                "equity": equity,
                "total_pnl": total_pnl,
                "day_change": (equity - ref) if ref is not None else None,
                "open_entry_fees": open_entry_fees,
                "realized_plus_unrealized": realized + unrealized,
                # Entry fees on OPEN lots hit cash immediately but enter realized only on close.
                "pnl_explained": realized + unrealized - open_entry_fees,
                "priced_positions": priced_n,
                "incomplete_open": incomplete_open,
                "open_positions": open_n,
            },
            "positions": rows[:200],
            "equity_curve": curve,
        }
    finally:
        session.close()


@router.get("/paper/portfolios/{code}/activity")
def get_paper_portfolio_activity(code: str, limit: int = 100) -> dict:
    """Virtual fill log (buys / sells) newest first, for the broker-style activity
    journal. Read-only; never a real venue.
    """
    from sqlalchemy import select

    from app.db.models import PaperOrder

    session = SessionLocal()
    try:
        portfolio = get_portfolio_by_code(session, code)
        if portfolio is None:
            raise HTTPException(status_code=404, detail="portfolio_not_found")
        orders = (
            session.execute(
                select(PaperOrder)
                .where(PaperOrder.portfolio_id == portfolio.id)
                .order_by(PaperOrder.created_at.desc())
                .limit(max(1, min(limit, 500)))
            )
            .scalars()
            .all()
        )
        return {
            "orders": [
                {
                    "id": o.id,
                    "position_id": o.position_id,
                    "time": o.created_at.isoformat(),
                    "symbol": o.symbol,
                    "timeframe": o.timeframe,
                    "side": o.side,
                    "requested_price": o.requested_price,
                    "filled_price": o.filled_price,
                    "qty": o.qty,
                    "notional": o.notional,
                    "fee": o.fee,
                    "status": o.status,
                    "reason": o.reason,
                }
                for o in orders
            ]
        }
    finally:
        session.close()


@router.get("/paper/portfolios/{code}")
def get_paper_portfolio(code: str) -> dict:
    session = SessionLocal()
    try:
        if code in ALL_PROFILES:
            ensure_portfolio(session, code)
            session.commit()
        portfolio = get_portfolio_by_code(session, code)
        if portfolio is None:
            raise HTTPException(status_code=404, detail="portfolio_not_found")
        positions = paper_engine.list_positions(session, portfolio_id=portfolio.id)
        perf = compute_portfolio_performance(session, portfolio, positions)
        return {
            "portfolio": _portfolio_dict(portfolio),
            "performance": _paper_perf_dict(perf),
            "positions": [_paper_position_dict(p) for p in positions[:100]],
        }
    finally:
        session.close()


@router.get("/shadow/stats")
def get_shadow_stats(portfolio_code: str | None = None) -> dict:
    """ShadowBroker counterfactual summary — hors cash."""
    session = SessionLocal()
    try:
        portfolio_id = None
        if portfolio_code:
            if portfolio_code in ALL_PROFILES:
                ensure_portfolio(session, portfolio_code)
                session.commit()
            p = get_portfolio_by_code(session, portfolio_code)
            if p is None:
                raise HTTPException(status_code=404, detail="portfolio_not_found")
            portfolio_id = p.id
        return shadow_stats(session, portfolio_id=portfolio_id)
    finally:
        session.close()


@router.get("/shadow/positions")
def get_shadow_positions(
    portfolio_code: str | None = None,
    status: str | None = None,
    limit: int = 50,
) -> dict:
    session = SessionLocal()
    try:
        portfolio_id = None
        if portfolio_code:
            p = get_portfolio_by_code(session, portfolio_code)
            if p is None:
                raise HTTPException(status_code=404, detail="portfolio_not_found")
            portfolio_id = p.id
        rows = list_shadows(
            session,
            portfolio_id=portfolio_id,
            status=status,
            limit=min(limit, 200),
        )
        return {"positions": [shadow_to_dict(r) for r in rows]}
    finally:
        session.close()


@router.get("/paper/propose")
def propose_paper_trade(
    symbol: str,
    timeframe: str = "1h",
    portfolio_code: str = "ICHIVOL_BASELINE_V1",
    rvol_low: float | None = None,
    rvol_significant: float | None = None,
    rvol_strong: float | None = None,
    rvol_anomaly: float | None = None,
    atr_dead_percentile: float | None = None,
    atr_extreme_percentile: float | None = None,
    atr_stop_multiplier: float | None = None,
) -> dict:
    """Dry-run paper order intent (qty/stop/TP) — read-only, never opens a position.

    Front flow: propose → user confirms → POST /paper/positions.
    """
    from app.paper.intent import propose_order_intent

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
        intent = propose_order_intent(session, row, portfolio_code=portfolio_code)
        return {
            "intent": intent.to_dict(),
            "pipeline": {
                "decision": row.pipeline.decision,
                "direction": row.pipeline.direction.value,
            },
        }
    finally:
        session.close()


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

    if (getattr(row, "signal_timing", None) or {}).get("stale"):
        raise HTTPException(
            status_code=422,
            detail="stale_data: provider candles are late/frozen, refusing to open on an outdated signal",
        )
    stop = row.atr.suggested_stop_distance if row.atr is not None else None
    session = SessionLocal()
    try:
        evidence_id = None
        if row.evidence is not None:
            from app.evidence.persistence import persist_evidence

            evidence_row = persist_evidence(
                session,
                report=row.evidence,
                decision=row.pipeline.decision,
                market_snapshot={
                    "price": row.price,
                    "volume_type": row.candles[-1].volume_type.value if row.candles else "NONE",
                },
            )
            evidence_id = evidence_row.id
            session.flush()

        position, created = paper_engine.open_user_confirmed(
            session,
            symbol=row.symbol,
            timeframe=timeframe,
            user_id=user_id,
            price=row.price,
            pipeline=row.pipeline,
            stop_distance=stop,
            evidence_id=evidence_id,
            signal_extra={
                "evidence_id": evidence_id,
                "context": row.context.to_dict() if row.context else None,
            },
        )
        if position is None:
            raise HTTPException(
                status_code=422,
                detail="not_actionable: pipeline.decision is WATCH/NO_TRADE, nothing to open",
            )
        if evidence_id and position.evidence_id is None:
            position.evidence_id = evidence_id
            session.commit()
        payload = _paper_position_dict(position)
        payload["created"] = created
        if not created:
            payload["already_open"] = True
        return payload
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
