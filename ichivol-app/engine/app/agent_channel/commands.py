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
    from app.strategy_lab.perf_db import experiment_dict, list_experiments

    session = SessionLocal()
    try:
        rows = list_experiments(
            session,
            symbol=args.get("symbol"),
            timeframe=args.get("timeframe"),
            ruleset_id=args.get("ruleset_id"),
            limit=int(args.get("limit", 50)),
        )
        return {"experiments": [experiment_dict(r) for r in rows], "count": len(rows)}
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
