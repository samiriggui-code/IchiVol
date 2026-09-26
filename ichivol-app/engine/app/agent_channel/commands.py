"""Agent command channel -- READ v1 (docs/HANDOFF-* agent channel brief,
2026-09-16): a small set of named, allowlisted commands that wrap ALREADY
EXISTING, already-tested engine functionality (scan_symbol, scan_watchlist,
experiments.compare, compute_correlation_matrix, REGISTRY ichimoku/rvol)
behind a uniform `{cmd, args} -> {ok, data|error}` calling
convention, instead of one HTTP route per capability.

Zero LLM here, zero new decision logic: every handler below is a thin
wrapper that calls the same functions app/api/routes.py already calls, and
returns the same response shapes (app/api/serializers.py) -- a command
channel for a calling agent (or a future non-HTTP client), not a second
decision engine. No handler here ever opens/closes a paper position or
writes anything beyond the same audit persistence `/decisions/{symbol}`
already does when `persist=true` (default `false` here, unlike the HTTP
route, since a command-channel caller is expected to probe more liberally
than a human clicking through the UI).
"""

from __future__ import annotations

import time
from dataclasses import fields, is_dataclass
from enum import Enum
from typing import Callable

from app.api.serializers import backtest_dict, detail_dict, metrics_dict, risk_dict, summary_dict
from app.backtest import experiments
from app.chart_objects.collect import collect_chart_objects
from app.chart_objects.draw import build_from_draw_args
from app.chart_objects.grounding import assert_object_grounded
from app.chart_objects.store import soft_delete_chart_object, upsert_chart_object
from app.chart_objects.types import ChartObjectType
from app.context.calendar import fetch_calendar_events
from app.context.news import fetch_news
from app.correlation.engine import compute_correlation_matrix
from app.cycle.closed_fetch import filter_closed_candles
from app.cycle.engine import CycleParams, compute_cycle_state
from app.cycle.study import CycleStudyParams, run_cycle_walk_forward
from app.db.session import SessionLocal
from app.indicators.atr import AtrParams
from app.indicators.registry import REGISTRY
from app.indicators.rvol import RvolParams
from app.market_data.resolve import ProviderNotWiredError, resolve_and_fetch
from app.screener.cache import screener_cache
from app.screener.persistence import persist_scan
from app.screener.service import scan_symbol
from app.strategy_lab.catalog import get_builtin_ruleset, list_builtin_rulesets
from app.strategy_lab.event_study import event_study_dict, run_event_study
from app.strategy_lab.ruleset import parse_ruleset
from app.strategy_lab.run_ruleset import ruleset_study_dict, run_ruleset_event_study
from app.structure.payload import build_structure_payload
from app.universe.catalog import default_watchlist


class CommandError(Exception):
    """A client-caused failure (bad/missing arg, unknown symbol, insufficient
    history, too many symbols) -- the registry turns this into a structured
    `{ok: false, error}` response instead of a raw 500."""


def _require_str(args: dict, key: str) -> str:
    value = args.get(key)
    if not isinstance(value, str) or not value.strip():
        raise CommandError(f"missing_or_invalid_arg: {key!r} must be a non-empty string")
    return value.strip()


def _state_to_dict(state: object) -> dict:
    if not is_dataclass(state):
        raise TypeError(f"expected a dataclass state, got {type(state)!r}")
    out: dict = {}
    for f in fields(state):
        value = getattr(state, f.name)
        out[f.name] = value.value if isinstance(value, Enum) else value
    return out


def _rvol_params_from_args(args: dict) -> RvolParams:
    d = RvolParams()
    low = args.get("rvol_low", d.low_threshold)
    significant = args.get("rvol_significant", d.significant_threshold)
    strong = args.get("rvol_strong", d.strong_threshold)
    anomaly = args.get("rvol_anomaly", d.anomaly_threshold)
    if not (0 <= low < significant < strong < anomaly):
        raise CommandError(
            "invalid_rvol_thresholds: expected 0 <= rvol_low < rvol_significant < rvol_strong < rvol_anomaly"
        )
    return RvolParams(
        low_threshold=low, significant_threshold=significant,
        strong_threshold=strong, anomaly_threshold=anomaly,
    )


def _atr_params_from_args(args: dict) -> AtrParams:
    d = AtrParams()
    dead = args.get("atr_dead_percentile", d.dead_percentile)
    extreme = args.get("atr_extreme_percentile", d.extreme_percentile)
    stop_multiplier = args.get("atr_stop_multiplier", d.stop_multiplier)
    if not (0 <= dead < extreme <= 1):
        raise CommandError(
            "invalid_atr_percentiles: expected 0 <= atr_dead_percentile < atr_extreme_percentile <= 1"
        )
    if stop_multiplier <= 0:
        raise CommandError("invalid_atr_stop_multiplier: must be > 0")
    return AtrParams(
        dead_percentile=dead, extreme_percentile=extreme, stop_multiplier=stop_multiplier,
    )


def cmd_scan_market(args: dict) -> dict:
    """Same payload as `GET /screener`'s cached path (no live scan on the
    request path unless `force`)."""
    timeframe = args.get("timeframe", "1h")
    force = bool(args.get("force", False))
    entry = None if force else screener_cache.get(timeframe)
    if entry is None:
        entry = screener_cache.refresh(timeframe)
    return {
        "timeframe": entry.timeframe,
        "computed_at": entry.computed_at,
        "cache_age_seconds": time.time() - entry.computed_at,
        "rows": [summary_dict(r) for r in entry.rows],
    }


def cmd_get_symbol_context(args: dict) -> dict:
    """Same payload as `GET /decisions/{symbol}` -- full detail (reasons,
    risks, invalidation, per-agent metadata, pipeline stages, risk hint)."""
    symbol = _require_str(args, "symbol").upper()
    timeframe = args.get("timeframe", "1h")
    limit = int(args.get("limit", 300))
    persist = bool(args.get("persist", False))
    try:
        row = scan_symbol(symbol, timeframe=timeframe, limit=limit)
    except ValueError as exc:
        raise CommandError(str(exc)) from exc

    if persist:
        session = SessionLocal()
        try:
            persist_scan(session, row)
        finally:
            session.close()

    return detail_dict(row)


def cmd_detect_signal(args: dict) -> dict:
    """Condensed verdict-only view: the pipeline's label + stage summaries +
    risk hint, no legacy-combiner detail (see `get_symbol_context` for that).
    """
    symbol = _require_str(args, "symbol").upper()
    timeframe = args.get("timeframe", "1h")
    try:
        row = scan_symbol(symbol, timeframe=timeframe)
    except ValueError as exc:
        raise CommandError(str(exc)) from exc

    return {
        "symbol": row.symbol,
        "timeframe": row.timeframe,
        "price": row.price,
        "decision": row.pipeline.decision,
        "direction": row.pipeline.direction.value,
        "stages": [
            {"id": s.id.value, "status": s.status.value, "summary": s.summary, "codes": s.codes}
            for s in row.pipeline.stages
        ],
        "risk": risk_dict(row),
    }


_DEFAULT_COMPARE_TIMEFRAMES = ["15m", "1h", "4h", "1d"]


def cmd_compare_timeframes(args: dict) -> dict:
    """Runs the same symbol through `scan_symbol` at several timeframes and
    returns each's screener-summary side by side -- one bad/insufficient
    timeframe never sinks the others (each entry carries its own error)."""
    symbol = _require_str(args, "symbol").upper()
    timeframes = args.get("timeframes") or _DEFAULT_COMPARE_TIMEFRAMES
    if not isinstance(timeframes, list) or not timeframes:
        raise CommandError("timeframes must be a non-empty list of timeframe strings")

    results: dict = {}
    for tf in timeframes:
        try:
            row = scan_symbol(symbol, timeframe=str(tf))
            results[str(tf)] = summary_dict(row)
        except ValueError as exc:
            results[str(tf)] = {"error": str(exc)}
    return {"symbol": symbol, "timeframes": results}


def cmd_run_backtest(args: dict) -> dict:
    """Same payload as `GET /backtest/{symbol}`."""
    symbol = _require_str(args, "symbol").upper()
    timeframe = args.get("timeframe", "1h")
    limit = int(args.get("limit", 1000))
    rvol_params = _rvol_params_from_args(args)
    atr_params = _atr_params_from_args(args)
    try:
        results = experiments.compare(
            symbol, timeframe=timeframe, limit=limit, rvol_params=rvol_params, atr_params=atr_params
        )
    except ValueError as exc:
        raise CommandError(str(exc)) from exc

    return {
        "symbol": symbol,
        "timeframe": timeframe,
        "experiments": {
            name: {
                "metrics": metrics_dict(exp.metrics, metrics_basis="net_v2"),
                "backtest": backtest_dict(exp.backtest),
            }
            for name, exp in results.items()
        },
    }


def cmd_run_event_study(args: dict) -> dict:
    """Same payload as `GET /event-study/{symbol}` (Strategy Lab Phase 1)."""
    symbol = _require_str(args, "symbol").upper()
    timeframe = str(args.get("timeframe", "1h"))
    limit = int(args.get("limit", 1000))
    variant = str(args.get("variant", experiments.PIPELINE))
    horizons_arg = args.get("horizons", [1, 3, 5, 10])
    if isinstance(horizons_arg, str):
        horizons = tuple(int(x.strip()) for x in horizons_arg.split(",") if x.strip())
    else:
        horizons = tuple(int(x) for x in horizons_arg)
    r_multiple = float(args.get("r_multiple", 1.0))
    include_events = bool(args.get("include_events", False))
    try:
        result = run_event_study(
            symbol,
            timeframe=timeframe,
            limit=limit,
            variant=variant,
            horizons=horizons,
            r_multiple=r_multiple,
        )
    except ValueError as exc:
        raise CommandError(str(exc)) from exc
    return event_study_dict(result, include_events=include_events)


def cmd_run_anomaly_regime_study(args: dict) -> dict:
    """Event study stratified by EventAnomaly regime — research only, never votes."""
    from app.events.regime_study import anomaly_regime_study_dict, run_anomaly_regime_study

    symbol = _require_str(args, "symbol").upper()
    timeframe = str(args.get("timeframe", "1h"))
    limit = int(args.get("limit", 1000))
    horizons_arg = args.get("horizons", [1, 3, 5, 10])
    if isinstance(horizons_arg, str):
        horizons = tuple(int(x.strip()) for x in horizons_arg.split(",") if x.strip())
    else:
        horizons = tuple(int(x) for x in horizons_arg)
    r_multiple = float(args.get("r_multiple", 1.0))
    min_signals = int(args.get("min_signals", 5))
    try:
        report = run_anomaly_regime_study(
            symbol,
            timeframe=timeframe,
            limit=limit,
            horizons=horizons,
            r_multiple=r_multiple,
            min_signals=min_signals,
        )
    except ValueError as exc:
        raise CommandError(str(exc)) from exc
    return anomaly_regime_study_dict(report)


def cmd_calibrate_anomaly_thresholds(args: dict) -> dict:
    """Suggest p99 anomaly gates from causal history — does not change live thresholds."""
    from app.events.calibrate import calibrate_anomaly_thresholds, calibration_report_dict
    from app.indicators.registry import REGISTRY

    symbol = _require_str(args, "symbol").upper()
    timeframe = str(args.get("timeframe", "1h"))
    limit = int(args.get("limit", 1000))
    try:
        _prov, _sym, candles = resolve_and_fetch(symbol, timeframe, limit)
    except (ValueError, ProviderNotWiredError) as exc:
        raise CommandError(str(exc)) from exc
    atr_states = REGISTRY.compute("atr", candles)
    report = calibrate_anomaly_thresholds(
        candles, atr_states, symbol=symbol, timeframe=timeframe
    )
    return calibration_report_dict(report)


def cmd_list_rulesets(_args: dict) -> dict:
    return {"rulesets": [r.to_dict() for r in list_builtin_rulesets()]}


def cmd_run_ruleset_event_study(args: dict) -> dict:
    """Same as `POST /ruleset/event-study` / `GET /ruleset/{id}/event-study`."""
    symbol = _require_str(args, "symbol").upper()
    timeframe = str(args.get("timeframe", "1h"))
    limit = int(args.get("limit", 1000))
    horizons_arg = args.get("horizons", [1, 3, 5, 10])
    if isinstance(horizons_arg, str):
        horizons = tuple(int(x.strip()) for x in horizons_arg.split(",") if x.strip())
    else:
        horizons = tuple(int(x) for x in horizons_arg)
    include_events = bool(args.get("include_events", False))
    with_backtest = bool(args.get("with_backtest", True))
    persist = bool(args.get("persist", False))
    try:
        if args.get("ruleset") is not None:
            ruleset = parse_ruleset(args["ruleset"])
        else:
            ruleset = get_builtin_ruleset(_require_str(args, "ruleset_id"))
        result = run_ruleset_event_study(
            ruleset,
            symbol,
            timeframe=timeframe,
            limit=limit,
            horizons=horizons,
            with_backtest=with_backtest,
        )
    except ValueError as exc:
        raise CommandError(str(exc)) from exc
    payload = ruleset_study_dict(result, include_events=include_events)
    if persist:
        from app.strategy_lab.perf_db import persist_study_result

        payload["experiment"] = persist_study_result(
            result,
            parameters={"limit": limit, "horizons": list(horizons), "source": "agent"},
        )
    return payload


def cmd_list_strategy_lab_experiments(args: dict) -> dict:
    from app.db.session import SessionLocal
    from app.strategy_lab.perf_db import experiments_dicts, list_experiments

    session = SessionLocal()
    try:
        rows = list_experiments(
            session,
            symbol=args.get("symbol"),
            timeframe=args.get("timeframe"),
            ruleset_id=args.get("ruleset_id"),
            hypothesis_id=args.get("hypothesis_id"),
            limit=int(args.get("limit", 50)),
        )
        return {"experiments": experiments_dicts(session, rows), "count": len(rows)}
    finally:
        session.close()


def cmd_run_ablation(args: dict) -> dict:
    from app.strategy_lab.ablation import ablation_dict, run_ablation

    symbol = _require_str(args, "symbol").upper()
    try:
        result = run_ablation(
            symbol,
            timeframe=str(args.get("timeframe", "1h")),
            limit=int(args.get("limit", 1000)),
            mode=str(args.get("mode", "cumulative")),
            layers=args.get("layers"),
            direction=str(args.get("direction", "LONG")),
            stop_atr=float(args.get("stop_atr", 1.0)),
            target_atr=float(args.get("target_atr", 2.0)),
            persist=bool(args.get("persist", False)),
        )
    except ValueError as exc:
        raise CommandError(str(exc)) from exc
    return ablation_dict(result)


def cmd_run_regime_slices(args: dict) -> dict:
    from app.strategy_lab.regime_slices import regime_slices_dict, run_regime_slices

    symbol = _require_str(args, "symbol").upper()
    try:
        report = run_regime_slices(
            symbol,
            timeframe=str(args.get("timeframe", "1h")),
            limit=int(args.get("limit", 1000)),
            ruleset_id=args.get("ruleset_id"),
            ruleset=args.get("ruleset"),
            persist=bool(args.get("persist", False)),
            deep_history=bool(args.get("deep_history", False)),
            years=float(args.get("years", 2.0)),
            dataset_id=(
                str(args["dataset_id"]).strip()
                if args.get("dataset_id") is not None
                else None
            ),
        )
    except ValueError as exc:
        raise CommandError(str(exc)) from exc
    return regime_slices_dict(report)


def cmd_run_walk_forward(args: dict) -> dict:
    from app.strategy_lab.walk_forward import run_walk_forward, walk_forward_dict

    symbol = _require_str(args, "symbol").upper()
    step = args.get("step_bars")
    try:
        report = run_walk_forward(
            symbol,
            timeframe=str(args.get("timeframe", "1h")),
            limit=int(args.get("limit", 1000)),
            ruleset_id=args.get("ruleset_id"),
            ruleset=args.get("ruleset"),
            mode=str(args.get("mode", "rolling")),
            train_bars=int(args.get("train_bars", 400)),
            test_bars=int(args.get("test_bars", 100)),
            step_bars=int(step) if step is not None else None,
            warmup_bars=int(args.get("warmup_bars", 52)),
            include_train=bool(args.get("include_train", True)),
            persist=bool(args.get("persist", False)),
            deep_history=bool(args.get("deep_history", False)),
            years=float(args.get("years", 2.0)),
            dataset_id=(
                str(args["dataset_id"]).strip()
                if args.get("dataset_id") is not None
                else None
            ),
        )
    except ValueError as exc:
        raise CommandError(str(exc)) from exc
    return walk_forward_dict(report)


def cmd_run_optimize(args: dict) -> dict:
    from app.strategy_lab.optimization import optimize_dict, run_optimize

    symbol = _require_str(args, "symbol").upper()
    try:
        report = run_optimize(
            symbol,
            timeframe=str(args.get("timeframe", "1h")),
            limit=int(args.get("limit", 1000)),
            ruleset_id=args.get("ruleset_id"),
            ruleset=args.get("ruleset"),
            grid=args.get("grid"),
            objective=str(args.get("objective", "expectancy")),
            min_trades=int(args.get("min_trades", 5)),
            warmup_bars=int(args.get("warmup_bars", 52)),
            persist_best=bool(args.get("persist_best", False)),
        )
    except ValueError as exc:
        raise CommandError(str(exc)) from exc
    return optimize_dict(report)


def cmd_run_walk_forward_opt(args: dict) -> dict:
    from app.strategy_lab.optimization import run_walk_forward_opt, walk_forward_opt_dict

    symbol = _require_str(args, "symbol").upper()
    step = args.get("step_bars")
    try:
        report = run_walk_forward_opt(
            symbol,
            timeframe=str(args.get("timeframe", "1h")),
            limit=int(args.get("limit", 1000)),
            ruleset_id=args.get("ruleset_id"),
            ruleset=args.get("ruleset"),
            mode=str(args.get("mode", "rolling")),
            train_bars=int(args.get("train_bars", 400)),
            test_bars=int(args.get("test_bars", 100)),
            step_bars=int(step) if step is not None else None,
            warmup_bars=int(args.get("warmup_bars", 52)),
            grid=args.get("grid"),
            objective=str(args.get("objective", "expectancy")),
            min_trades=int(args.get("min_trades", 5)),
            persist=bool(args.get("persist", False)),
        )
    except ValueError as exc:
        raise CommandError(str(exc)) from exc
    return walk_forward_opt_dict(report)


_MAX_CORRELATION_SYMBOLS = 40


def cmd_list_provider_capabilities(args: dict) -> dict:
    """V3 — declared provider capabilities (inventory; not a live guarantee)."""
    from app.market_data.capabilities import get_capabilities, list_capabilities

    provider = args.get("provider")
    if provider:
        caps = get_capabilities(str(provider).strip().lower())
        if caps is None:
            raise CommandError(f"unknown provider: {provider}")
        providers = [caps.to_dict()]
    else:
        providers = [c.to_dict() for c in list_capabilities()]
    return {
        "providers": providers,
        "disclaimer": (
            "Provider capabilities — declarative inventory of what the "
            "engine wires today; not a live data guarantee."
        ),
    }


def cmd_get_correlations(args: dict) -> dict:
    """Same payload as `GET /correlations`. `symbols` accepts either a
    comma-separated string (HTTP-style) or a JSON list (command-style)."""
    symbols_arg = args.get("symbols")
    if isinstance(symbols_arg, str):
        symbol_list = [s.strip().upper() for s in symbols_arg.split(",") if s.strip()]
    elif isinstance(symbols_arg, list):
        symbol_list = [str(s).strip().upper() for s in symbols_arg if str(s).strip()]
    else:
        symbol_list = list(default_watchlist())

    timeframe = args.get("timeframe", "1h")
    limit = int(args.get("limit", 300))
    method = args.get("method", "log_returns")

    if not symbol_list:
        raise CommandError("no_symbols: provide at least one symbol or omit `symbols` for the default watchlist")
    if len(symbol_list) > _MAX_CORRELATION_SYMBOLS:
        raise CommandError(f"too_many_symbols: max {_MAX_CORRELATION_SYMBOLS} symbols per request")

    try:
        result = compute_correlation_matrix(symbol_list, timeframe=timeframe, limit=limit, method=method)
    except ValueError as exc:
        raise CommandError(str(exc)) from exc

    return {
        "timeframe": result.timeframe,
        "method": result.method,
        "symbols": result.symbols,
        "sample_size": result.sample_size,
        "matrix": result.matrix,
        "skipped": [{"symbol": s.symbol, "reason": s.reason} for s in result.skipped],
    }


def cmd_get_cycle_state(args: dict) -> dict:
    """Same payload as `GET /cycle/{symbol}` — observe-only CycleState."""
    symbol = _require_str(args, "symbol").upper()
    timeframe = args.get("timeframe", "1h")
    if not isinstance(timeframe, str) or not timeframe.strip():
        raise CommandError("missing_or_invalid_arg: 'timeframe' must be a non-empty string")
    limit = int(args.get("limit", 300))
    window = int(args.get("window", 128))
    if window < 32 or window > 512:
        raise CommandError("window must be in [32, 512]")
    if limit < window:
        raise CommandError("limit must be >= window")
    now_arg = args.get("now")
    now = int(now_arg) if now_arg is not None else None

    try:
        provider, provider_symbol, candles = resolve_and_fetch(symbol, timeframe, min(limit, 1000))
        candles, now_s = filter_closed_candles(candles, timeframe, now=now)
    except ProviderNotWiredError as exc:
        raise CommandError(str(exc)) from exc
    except ValueError as exc:
        raise CommandError(str(exc)) from exc

    state = compute_cycle_state(candles, CycleParams(window=window))
    return {
        "symbol": symbol,
        "timeframe": timeframe,
        "provider": provider.id,
        "provider_symbol": provider_symbol,
        "window": window,
        "now": now_s,
        "n_bars": len(candles),
        "cycle": state.to_dict(),
        "disclaimer": (
            "Observe-only CycleState on closed candles. Not a trade signal. "
            "methods_agreement is period consensus, not probability of profit."
        ),
    }


def cmd_run_cycle_study(args: dict) -> dict:
    """Regime-filter study — same as GET /cycle/{symbol}/study (closed bars)."""
    symbol = _require_str(args, "symbol").upper()
    timeframe = args.get("timeframe", "1h")
    if not isinstance(timeframe, str) or not timeframe.strip():
        raise CommandError("missing_or_invalid_arg: 'timeframe' must be a non-empty string")
    limit = int(args.get("limit", 500))
    window = int(args.get("window", 96))
    horizon = int(args.get("horizon", 8))
    if window < 32 or window > 512:
        raise CommandError("window must be in [32, 512]")
    if horizon < 1 or horizon > 64:
        raise CommandError("horizon must be in [1, 64]")
    now_arg = args.get("now")
    now = int(now_arg) if now_arg is not None else None

    try:
        provider, provider_symbol, candles = resolve_and_fetch(symbol, timeframe, min(limit, 1000))
        candles, now_s = filter_closed_candles(candles, timeframe, now=now)
    except ProviderNotWiredError as exc:
        raise CommandError(str(exc)) from exc
    except ValueError as exc:
        raise CommandError(str(exc)) from exc

    study = run_cycle_walk_forward(
        candles,
        CycleStudyParams(window=window, horizon=horizon),
    )
    return {
        "symbol": symbol,
        "timeframe": timeframe,
        "provider": provider.id,
        "provider_symbol": provider_symbol,
        "now": now_s,
        "n_closed_bars": len(candles),
        "study": study,
        "disclaimer": (
            "Research only (independent future ER + surrogates). Not a trade signal. "
            "Does not modify the decision pipeline."
        ),
    }


def cmd_calculate_ichimoku(args: dict) -> dict:
    """Raw indicator only -- no RVOL, no pipeline, no decision. For a caller
    that wants the Ichimoku state itself (tenkan/kijun/cloud/score/...), not
    an interpreted trade decision."""
    symbol = _require_str(args, "symbol").upper()
    timeframe = args.get("timeframe", "1h")
    limit = int(args.get("limit", 300))
    try:
        provider, _provider_symbol, candles = resolve_and_fetch(symbol, timeframe, limit)
    except ValueError as exc:
        raise CommandError(str(exc)) from exc
    if len(candles) < 2:
        raise CommandError(f"not enough candles returned for {symbol} {timeframe}")

    state = REGISTRY.compute("ichimoku", candles)[-1]
    return {"symbol": symbol, "timeframe": timeframe, "provider": provider.id, **_state_to_dict(state)}


def cmd_calculate_rvol(args: dict) -> dict:
    """Raw indicator only -- no pipeline, no decision."""
    symbol = _require_str(args, "symbol").upper()
    timeframe = args.get("timeframe", "1h")
    limit = int(args.get("limit", 300))
    try:
        provider, _provider_symbol, candles = resolve_and_fetch(symbol, timeframe, limit)
    except ValueError as exc:
        raise CommandError(str(exc)) from exc
    if len(candles) < 2:
        raise CommandError(f"not enough candles returned for {symbol} {timeframe}")

    state = REGISTRY.compute("rvol", candles)[-1]
    return {"symbol": symbol, "timeframe": timeframe, "provider": provider.id, **_state_to_dict(state)}


def cmd_get_news(args: dict) -> dict:
    """Same payload as `GET /context/news` -- read-only, opt-in context,
    never touches the decision pipeline."""
    limit = int(args.get("limit", 20))
    sources = args.get("sources")
    if isinstance(sources, str):
        sources = [s.strip() for s in sources.split(",") if s.strip()]
    elif not isinstance(sources, list):
        sources = None
    items = fetch_news(limit=limit, sources=sources)
    return {
        "items": [
            {"title": i.title, "url": i.url, "source": i.source, "published_at": i.published_at}
            for i in items
        ]
    }


def cmd_get_calendar(args: dict) -> dict:
    """Same payload as `GET /context/calendar` -- read-only, opt-in context,
    never touches the decision pipeline."""
    limit = args.get("limit")
    events = fetch_calendar_events(limit=int(limit) if limit is not None else None)
    return {
        "events": [
            {
                "title": e.title, "country": e.country, "date": e.date,
                "impact": e.impact, "forecast": e.forecast, "previous": e.previous,
            }
            for e in events
        ]
    }


def cmd_get_event_context(args: dict) -> dict:
    """Event Intelligence PHASE 7 — anomaly + causal news/calendar matches.

    Read-only. Never votes BUY/SELL. Prefer calling this for Claude explain;
    decision pipeline remains unchanged.
    """
    from app.events.anomaly import anomaly_observation_dict, detect_anomaly
    from app.events.context import build_event_context
    from app.events.correlate import event_context_dict

    symbol = _require_str(args, "symbol").upper()
    timeframe = str(args.get("timeframe", "1h"))
    limit = int(args.get("limit", 300))
    try:
        _prov, _sym, candles = resolve_and_fetch(symbol, timeframe, limit)
    except (ValueError, ProviderNotWiredError) as exc:
        raise CommandError(str(exc)) from exc

    rvol_states = REGISTRY.compute("rvol", candles)
    atr_states = REGISTRY.compute("atr", candles)
    rvol_f = rvol_states[-1].rvol if rvol_states else None
    atr_f = float(atr_states[-1].atr) if atr_states and atr_states[-1].atr else None

    anomaly = detect_anomaly(
        candles, symbol=symbol, timeframe=timeframe, rvol=rvol_f, atr=atr_f
    )
    include_news = bool(args.get("include_news", True))
    include_macro = bool(args.get("include_macro", True))
    bundle = build_event_context(
        anomaly, include_news=include_news, include_macro=include_macro
    )
    payload = event_context_dict(bundle) or {}
    payload["anomaly"] = anomaly_observation_dict(bundle.anomaly)
    return payload


def cmd_get_family_weights(args: dict) -> dict:
    """T5a — versioned family-weight observation from live pipeline.

    Read-only. Never alters decision or confidence. Uses scan_symbol so the
    observation matches the HTTP decision detail payload.
    """
    from app.confluence.observe import family_weights_observation_dict

    symbol = _require_str(args, "symbol").upper()
    timeframe = str(args.get("timeframe", "1h"))
    limit = int(args.get("limit", 300))
    try:
        row = scan_symbol(symbol, timeframe=timeframe, limit=limit)
    except (ValueError, ProviderNotWiredError) as exc:
        raise CommandError(str(exc)) from exc
    fw = family_weights_observation_dict(getattr(row, "family_weights", None))
    return {
        "symbol": row.symbol,
        "timeframe": row.timeframe,
        "decision": row.decision.decision,
        "confidence": row.decision.confidence,
        "pipeline_decision": row.pipeline.decision,
        "family_weights": fw,
    }


def cmd_list_family_weight_profiles(args: dict) -> dict:
    """T5b — list named family-weight profiles (read-only catalog)."""
    from app.confluence.profiles import list_family_weight_profiles

    profiles = [
        {
            "id": p.id,
            "label": p.label,
            "description": p.description,
            "version": p.config.version,
            "weights": dict(p.config.weights),
        }
        for p in list_family_weight_profiles()
    ]
    return {
        "profiles": profiles,
        "disclaimer": (
            "Family weight profiles — observation / Lab only; "
            "not applied as live decision scores."
        ),
    }


def cmd_compare_family_weights(args: dict) -> dict:
    """T5b — compare all weight profiles on the live pipeline (observation)."""
    from app.confluence.compare import compare_family_weight_profiles

    symbol = _require_str(args, "symbol").upper()
    timeframe = str(args.get("timeframe", "1h"))
    limit = int(args.get("limit", 300))
    try:
        row = scan_symbol(symbol, timeframe=timeframe, limit=limit)
    except (ValueError, ProviderNotWiredError) as exc:
        raise CommandError(str(exc)) from exc
    payload = compare_family_weight_profiles(row.pipeline)
    payload["symbol"] = row.symbol
    payload["timeframe"] = row.timeframe
    payload["decision"] = row.decision.decision
    payload["confidence"] = row.decision.confidence
    return payload


def cmd_run_family_weights_study(args: dict) -> dict:
    """T5b — historical profile study on BUY/SELL pipeline bars (observation)."""
    from app.confluence.study import run_family_weights_study

    symbol = _require_str(args, "symbol").upper()
    timeframe = str(args.get("timeframe", "1h"))
    limit = int(args.get("limit", 500))
    step = int(args.get("step", 1))
    sample_limit = int(args.get("sample_limit", 20))
    try:
        _prov, _sym, candles = resolve_and_fetch(symbol, timeframe, limit)
    except (ValueError, ProviderNotWiredError) as exc:
        raise CommandError(str(exc)) from exc
    report = run_family_weights_study(
        candles,
        symbol=symbol,
        timeframe=timeframe,
        step=step,
        sample_limit=sample_limit,
    )
    return report.to_dict()


def cmd_run_feature_redundancy_study(args: dict) -> dict:
    """T10c — pairwise boolean feature redundancy (observation, no auto-reject)."""
    from app.agents.types import Direction
    from app.strategy_lab.redundancy import run_feature_redundancy_study

    symbol = _require_str(args, "symbol").upper()
    timeframe = str(args.get("timeframe", "1h"))
    limit = int(args.get("limit", 500))
    direction_raw = str(args.get("direction", "LONG")).upper()
    try:
        direction = Direction(direction_raw)
    except ValueError as exc:
        raise CommandError("direction must be LONG, SHORT, or NEUTRAL") from exc
    keys_arg = args.get("keys")
    key_list = None
    if keys_arg is not None:
        if isinstance(keys_arg, str):
            key_list = [k.strip() for k in keys_arg.split(",") if k.strip()]
        elif isinstance(keys_arg, list):
            key_list = [str(k) for k in keys_arg]
        else:
            raise CommandError("keys must be a comma-string or list")
    min_true = int(args.get("min_true", 5))
    top_n = int(args.get("top_n", 20))
    try:
        _prov, _sym, candles = resolve_and_fetch(symbol, timeframe, limit)
    except (ValueError, ProviderNotWiredError) as exc:
        raise CommandError(str(exc)) from exc
    try:
        report = run_feature_redundancy_study(
            candles,
            symbol=symbol,
            timeframe=timeframe,
            direction=direction,
            keys=key_list,
            min_true=min_true,
            top_n=top_n,
        )
    except ValueError as exc:
        raise CommandError(str(exc)) from exc
    return report.to_dict()


def cmd_run_ablation_oos_study(args: dict) -> dict:
    """T9g — ablation × walk-forward OOS (observation; no FeatureStatus mutation)."""
    from app.agents.types import Direction
    from app.strategy_lab.ablation_oos import run_ablation_oos_study_on_candles
    from app.strategy_lab.deep_history import resolve_lab_history

    symbol = _require_str(args, "symbol").upper()
    timeframe = str(args.get("timeframe", "1h"))
    limit = int(args.get("limit", 500))
    compare_mode = str(args.get("compare_mode", "additive"))
    ladder = str(args.get("ladder", "default"))
    direction_raw = str(args.get("direction", "LONG")).upper()
    try:
        direction = Direction(direction_raw)
    except ValueError as exc:
        raise CommandError("direction must be LONG, SHORT, or NEUTRAL") from exc
    try:
        bundle = resolve_lab_history(
            symbol,
            timeframe,
            limit=limit,
            deep_history=bool(args.get("deep_history", False)),
            years=float(args.get("years", 2.0)),
            dataset_id=(
                str(args["dataset_id"]).strip()
                if args.get("dataset_id") is not None
                else None
            ),
        )
    except (ValueError, ProviderNotWiredError) as exc:
        raise CommandError(str(exc)) from exc
    try:
        report = run_ablation_oos_study_on_candles(
            bundle.candles,
            symbol=symbol,
            timeframe=timeframe,
            compare_mode=compare_mode,
            ladder=ladder,
            direction=direction,
            train_bars=int(args.get("train_bars", 100)),
            test_bars=int(args.get("test_bars", 40)),
            step_bars=(int(args["step_bars"]) if args.get("step_bars") is not None else None),
            warmup_bars=int(args.get("warmup_bars", 52)),
            min_oos_trades=int(args.get("min_oos_trades", 30)),
            stop_atr=float(args.get("stop_atr", 1.0)),
            target_atr=float(args.get("target_atr", 2.0)),
            hypothesis_id=(
                str(args["hypothesis_id"]).strip()
                if args.get("hypothesis_id") is not None
                else None
            ),
            dataset_id=bundle.dataset_id,
            quality_report=bundle.quality,
            data_warning=bundle.data_warning,
            history_span_seconds=bundle.history_span_seconds,
            history_warning=bundle.history_warning,
        )
    except ValueError as exc:
        raise CommandError(str(exc)) from exc
    return report.to_dict()


def cmd_compare_trade_cvd(args: dict) -> dict:
    """Binance trade CVD vs kline CVD — Lab research; never pipeline vote."""
    from app.market_data.timeframes import TF_SECONDS
    from app.microstructure.binance_trades import fetch_binance_agg_trades
    from app.microstructure.trade_cvd import compare_kline_vs_trade_cvd
    from app.universe.catalog import get_instrument

    symbol = _require_str(args, "symbol").upper()
    timeframe = str(args.get("timeframe", "1h"))
    limit = int(args.get("limit", 24))
    max_trade_pages = int(args.get("max_trade_pages", 10))
    sample_limit = int(args.get("sample_limit", 20))
    if limit < 2 or limit > 48:
        raise CommandError("limit must be between 2 and 48")
    if max_trade_pages < 1 or max_trade_pages > 20:
        raise CommandError("max_trade_pages must be between 1 and 20")
    if timeframe not in TF_SECONDS:
        raise CommandError(f"timeframe must be one of {sorted(TF_SECONDS)}")
    instrument = get_instrument(symbol)
    if instrument is None:
        raise CommandError(f"unknown symbol: {symbol}")
    if instrument.provider != "binance":
        raise CommandError("trade CVD compare requires a binance-wired symbol")
    try:
        _prov, provider_symbol, candles = resolve_and_fetch(symbol, timeframe, limit)
    except (ValueError, ProviderNotWiredError) as exc:
        raise CommandError(str(exc)) from exc
    if not candles:
        raise CommandError("no candles")
    tf_sec = TF_SECONDS[timeframe]
    start_ms = int(candles[0].time) * 1000
    end_ms = (int(candles[-1].time) + tf_sec) * 1000
    try:
        trades = fetch_binance_agg_trades(
            provider_symbol,
            start_ms,
            end_ms,
            max_pages=max_trade_pages,
        )
    except Exception as exc:
        raise CommandError(f"aggTrades fetch failed: {exc}") from exc
    report = compare_kline_vs_trade_cvd(
        candles,
        trades,
        symbol=symbol,
        timeframe=timeframe,
        tf_seconds=tf_sec,
        sample_limit=sample_limit,
    )
    return report.to_dict()


def cmd_build_audit_report(args: dict) -> dict:
    """T6 — post-outcome AuditReport for one ruleset backtest trade.

    Read-only. Hypotheses stay ``proposed`` — never applied to prod strategy.
    """
    from app.auditor import build_audit_report_from_trade
    from app.strategy_lab.catalog import get_builtin_ruleset
    from app.strategy_lab.ruleset import parse_ruleset
    from app.strategy_lab.ruleset_backtest import run_ruleset_backtest_on_candles

    symbol = _require_str(args, "symbol").upper()
    timeframe = str(args.get("timeframe", "1h"))
    limit = int(args.get("limit", 300))
    trade_index = int(args.get("trade_index", 0))
    ruleset_id = args.get("ruleset_id")
    ruleset_raw = args.get("ruleset")
    if ruleset_raw is not None:
        try:
            ruleset = parse_ruleset(ruleset_raw)
        except (TypeError, ValueError) as exc:
            raise CommandError(f"invalid_ruleset: {exc}") from exc
        rid = getattr(ruleset, "id", None)
    elif ruleset_id:
        try:
            ruleset = get_builtin_ruleset(str(ruleset_id))
        except ValueError as exc:
            raise CommandError(str(exc)) from exc
        rid = str(ruleset_id)
    else:
        raise CommandError("missing_or_invalid_arg: ruleset_id or ruleset required")
    try:
        _prov, _sym, candles = resolve_and_fetch(symbol, timeframe, limit)
    except (ValueError, ProviderNotWiredError) as exc:
        raise CommandError(str(exc)) from exc
    result = run_ruleset_backtest_on_candles(candles, ruleset, symbol=symbol, timeframe=timeframe)
    if not result.details:
        raise CommandError("no_trades: ruleset produced zero trades on this window")
    if trade_index < 0 or trade_index >= len(result.details):
        raise CommandError(
            f"trade_index_out_of_range: {trade_index} (n={len(result.details)})"
        )
    report = build_audit_report_from_trade(
        result.details[trade_index],
        symbol=symbol,
        timeframe=timeframe,
        ruleset_id=rid,
        trade_index=trade_index,
    )
    payload = report.to_dict()
    payload["n_trades"] = len(result.details)
    return payload


def cmd_run_monte_carlo(args: dict) -> dict:
    """T7 — bootstrap Monte Carlo / risk-of-ruin on ruleset net trade returns.

    Research only. Requires enough trades (min_trades, default 20).
    """
    import math

    from app.risk.monte_carlo import run_monte_carlo
    from app.strategy_lab.catalog import get_builtin_ruleset
    from app.strategy_lab.ruleset import parse_ruleset
    from app.strategy_lab.ruleset_backtest import run_ruleset_backtest_on_candles

    symbol = _require_str(args, "symbol").upper()
    timeframe = str(args.get("timeframe", "1h"))
    limit = int(args.get("limit", 1000))
    n_paths = int(args.get("n_paths", 1000))
    seed = int(args.get("seed", 42))
    ruin_floor = float(args.get("ruin_floor", 0.5))
    min_trades = int(args.get("min_trades", 20))
    ruleset_id = args.get("ruleset_id")
    ruleset_raw = args.get("ruleset")
    if ruleset_raw is not None:
        try:
            ruleset = parse_ruleset(ruleset_raw)
        except (TypeError, ValueError) as exc:
            raise CommandError(f"invalid_ruleset: {exc}") from exc
        rid = getattr(ruleset, "id", None)
    elif ruleset_id:
        try:
            ruleset = get_builtin_ruleset(str(ruleset_id))
        except ValueError as exc:
            raise CommandError(str(exc)) from exc
        rid = str(ruleset_id)
    else:
        raise CommandError("missing_or_invalid_arg: ruleset_id or ruleset required")
    try:
        _prov, _sym, candles = resolve_and_fetch(symbol, timeframe, limit)
    except (ValueError, ProviderNotWiredError) as exc:
        raise CommandError(str(exc)) from exc
    result = run_ruleset_backtest_on_candles(
        candles, ruleset, symbol=symbol, timeframe=timeframe
    )
    net_rets = [math.exp(d.trade.net_log_return) - 1.0 for d in result.details]
    report = run_monte_carlo(
        net_rets,
        n_paths=n_paths,
        seed=seed,
        ruin_floor=ruin_floor,
        min_trades=min_trades,
    )
    payload = report.to_dict()
    payload["symbol"] = symbol
    payload["timeframe"] = timeframe
    payload["ruleset_id"] = rid
    return payload


def cmd_list_condition_catalog(args: dict) -> dict:
    """T3d — CONDITION_REGISTRY catalog for NL→DSL grounding (read-only)."""
    from app.strategy_lab.propose_edit import condition_catalog

    return {
        "conditions": condition_catalog(),
        "disclaimer": (
            "Condition catalog for Lab / Copilot — does not change live strategy."
        ),
    }


def cmd_propose_ruleset_edit(args: dict) -> dict:
    """T3d — propose a validated ruleset patch/candidate (status=proposed only)."""
    from app.strategy_lab.propose_edit import propose_ruleset_edit

    base_ruleset_id = args.get("base_ruleset_id")
    if base_ruleset_id is not None:
        base_ruleset_id = str(base_ruleset_id)
    base_ruleset = args.get("base_ruleset")
    patch = args.get("patch")
    patches = args.get("patches")
    ruleset = args.get("ruleset")
    try:
        return propose_ruleset_edit(
            base_ruleset_id=base_ruleset_id,
            base_ruleset=base_ruleset if isinstance(base_ruleset, dict) else None,
            patch=patch if isinstance(patch, dict) else None,
            patches=patches if isinstance(patches, list) else None,
            ruleset=ruleset if isinstance(ruleset, dict) else None,
        )
    except (TypeError, ValueError) as exc:
        raise CommandError(str(exc)) from exc


def cmd_propose_experiment_plan(args: dict) -> dict:
    """Researcher — AuditReport hypotheses → Lab tool plan (proposed only).

    Does not run studies or write Perf DB. Human/Claude executes steps.
    """
    from app.researcher import propose_experiment_plan

    report = args.get("audit_report")
    if not isinstance(report, dict):
        raise CommandError("missing_or_invalid_arg: audit_report object required")
    hypothesis_ids = args.get("hypothesis_ids")
    if hypothesis_ids is not None and not isinstance(hypothesis_ids, list):
        raise CommandError("hypothesis_ids must be a list of str")
    try:
        plan = propose_experiment_plan(
            report,
            hypothesis_ids=[str(x) for x in hypothesis_ids] if hypothesis_ids else None,
        )
    except ValueError as exc:
        raise CommandError(str(exc)) from exc
    return plan.to_dict()


def cmd_filter_backtest_overlay(args: dict) -> dict:
    """T4b — backtest overlay with structured filters for Claude (read-only).

    Same payload as POST /strategy-lab/backtest-overlay. Does not change fills.
    """
    from app.api.backtest_overlay import build_backtest_overlay_payload
    from app.strategy_lab.catalog import get_builtin_ruleset
    from app.strategy_lab.ruleset import parse_ruleset

    symbol = _require_str(args, "symbol").upper()
    timeframe = str(args.get("timeframe", "1h"))
    limit = int(args.get("limit", 300))
    outcome = str(args.get("outcome", "all"))
    exit_reason = args.get("exit_reason")
    if exit_reason is not None:
        exit_reason = str(exit_reason)
    direction = args.get("direction")
    if direction is not None:
        direction = str(direction)
    why_entered_key = args.get("why_entered_key")
    if why_entered_key is not None:
        why_entered_key = str(why_entered_key).strip() or None
    regime_label = args.get("regime_label")
    if regime_label is not None:
        regime_label = str(regime_label).strip() or None
    include_rejected = bool(args.get("include_rejected", True))

    try:
        if args.get("ruleset") is not None:
            ruleset = parse_ruleset(args["ruleset"])
        else:
            ruleset = get_builtin_ruleset(_require_str(args, "ruleset_id"))
        _prov, _sym, candles = resolve_and_fetch(symbol, timeframe, limit)
    except (ValueError, ProviderNotWiredError) as exc:
        raise CommandError(str(exc)) from exc

    try:
        return build_backtest_overlay_payload(
            symbol=symbol,
            timeframe=timeframe,
            candles=candles,
            ruleset=ruleset,
            outcome=outcome,
            exit_reason=exit_reason,
            direction=direction,
            why_entered_key=why_entered_key,
            regime_label=regime_label,
            include_rejected=include_rejected,
        )
    except Exception as exc:
        # HTTPException from validate → CommandError
        from fastapi import HTTPException

        if isinstance(exc, HTTPException):
            raise CommandError(str(exc.detail)) from exc
        raise


def cmd_list_tools(_args: dict) -> dict:
    # Populated at module load time by registry.py (which imports this
    # module and appends `list_tools` itself once every spec is built) --
    # kept as a plain function here so `list_tools` shows up in TOOLS like
    # every other command, satisfying the brief's allowlist verbatim.
    from app.agent_channel.registry import list_tool_specs

    return {"tools": list_tool_specs()}


def cmd_get_structure(args: dict) -> dict:
    """Same payload as GET /structure/{symbol} — analysis only, no draws."""
    symbol = _require_str(args, "symbol").upper()
    timeframe = args.get("timeframe", "1h")
    limit = int(args.get("limit", 300))
    include_pytrendline = bool(args.get("include_pytrendline", False))
    try:
        return build_structure_payload(
            symbol=symbol,
            timeframe=timeframe,
            limit=limit,
            include_pytrendline=include_pytrendline,
        )
    except ProviderNotWiredError as exc:
        raise CommandError(str(exc)) from exc
    except ValueError as exc:
        raise CommandError(str(exc)) from exc


def cmd_get_chart_objects(args: dict) -> dict:
    """Same payload as GET /chart-objects/{symbol} (ENGINE + USER/CLAUDE store).

    Default sources match HTTP: ``engine`` only. Pass ``sources`` explicitly
    to include persisted overlays (e.g. ``engine,user,claude``).
    """
    symbol = _require_str(args, "symbol").upper()
    timeframe = args.get("timeframe", "1h")
    limit = int(args.get("limit", 300))
    sources = args.get("sources", "engine")
    include_pytrendline = bool(args.get("include_pytrendline", False))
    try:
        return collect_chart_objects(
            symbol=symbol,
            timeframe=timeframe,
            limit=limit,
            sources=sources,
            include_pytrendline=include_pytrendline,
        )
    except ProviderNotWiredError as exc:
        raise CommandError(str(exc)) from exc
    except ValueError as exc:
        raise CommandError(str(exc)) from exc


def _draw_and_persist(obj_type_value: str, args: dict) -> dict:
    try:
        obj_type = ChartObjectType(obj_type_value)
        # Agent channel always stamps source=claude (no USER impersonation).
        obj = build_from_draw_args(obj_type, args, agent_channel=True)
    except ValueError as exc:
        raise CommandError(str(exc)) from exc

    # Anti-hallucination: times/prices must sit on the real OHLCV series.
    limit = int(args.get("limit") or 500)
    if limit < 50 or limit > 5000:
        limit = 500
    try:
        _provider, _psym, candles = resolve_and_fetch(obj.symbol, obj.timeframe, limit)
        assert_object_grounded(obj, candles)
    except ProviderNotWiredError as exc:
        raise CommandError(str(exc)) from exc
    except ValueError as exc:
        raise CommandError(str(exc)) from exc

    session = SessionLocal()
    try:
        saved = upsert_chart_object(session, obj)
        session.commit()
        return {"object": saved.to_dict(), "upserted": True}
    except ValueError as exc:
        session.rollback()
        raise CommandError(str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        raise CommandError(f"persist_failed: {exc}") from exc
    finally:
        session.close()


def cmd_draw_horizontal_line(args: dict) -> dict:
    return _draw_and_persist("horizontal_line", args)


def cmd_draw_trend_line(args: dict) -> dict:
    return _draw_and_persist("trend_line", args)


def cmd_draw_ray(args: dict) -> dict:
    return _draw_and_persist("ray", args)


def cmd_draw_zone(args: dict) -> dict:
    return _draw_and_persist("zone", args)


def cmd_draw_rectangle(args: dict) -> dict:
    return _draw_and_persist("rectangle", args)


def cmd_draw_channel(args: dict) -> dict:
    return _draw_and_persist("channel", args)


def cmd_draw_marker(args: dict) -> dict:
    return _draw_and_persist("marker", args)


def cmd_draw_text(args: dict) -> dict:
    return _draw_and_persist("text", args)


def cmd_draw_entry(args: dict) -> dict:
    return _draw_and_persist("entry", args)


def cmd_draw_stop(args: dict) -> dict:
    return _draw_and_persist("stop", args)


def cmd_draw_target(args: dict) -> dict:
    return _draw_and_persist("target", args)


def cmd_delete_chart_object(args: dict) -> dict:
    """Soft-delete a CLAUDE overlay. USER deletes are not allowed via agent."""
    object_id = _require_str(args, "id")
    # Agent may only delete its own overlays (source=claude).
    source = "claude"
    if args.get("source") not in (None, "", "claude"):
        raise CommandError(
            "agent delete_chart_object only deletes source=claude overlays"
        )
    session = SessionLocal()
    try:
        deleted = soft_delete_chart_object(session, object_id, source=source)
        session.commit()
        if not deleted:
            raise CommandError(f"not_found: chart object {object_id!r} (claude)")
        return {"id": object_id, "deleted": True, "source": source}
    except CommandError:
        session.rollback()
        raise
    except Exception as exc:  # noqa: BLE001
        session.rollback()
        raise CommandError(f"delete_failed: {exc}") from exc
    finally:
        session.close()


Handler = Callable[[dict], dict]
