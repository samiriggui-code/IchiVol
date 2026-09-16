"""Agent command channel -- READ v1 (docs/HANDOFF-* agent channel brief,
2026-09-16): a small set of named, allowlisted commands that wrap ALREADY
EXISTING, already-tested engine functionality (scan_symbol, scan_watchlist,
experiments.compare, compute_correlation_matrix, compute_ichimoku,
compute_rvol) behind a uniform `{cmd, args} -> {ok, data|error}` calling
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
from app.correlation.engine import compute_correlation_matrix
from app.db.session import SessionLocal
from app.indicators.atr import AtrParams
from app.indicators.ichimoku import compute_ichimoku
from app.indicators.rvol import RvolParams, compute_rvol
from app.market_data.resolve import resolve_and_fetch
from app.screener.cache import screener_cache
from app.screener.persistence import persist_scan
from app.screener.service import scan_symbol
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
            name: {"metrics": metrics_dict(exp.metrics), "backtest": backtest_dict(exp.backtest)}
            for name, exp in results.items()
        },
    }


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

    state = compute_ichimoku(candles)[-1]
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

    state = compute_rvol(candles)[-1]
    return {"symbol": symbol, "timeframe": timeframe, "provider": provider.id, **_state_to_dict(state)}


def cmd_list_tools(_args: dict) -> dict:
    # Populated at module load time by registry.py (which imports this
    # module and appends `list_tools` itself once every spec is built) --
    # kept as a plain function here so `list_tools` shows up in TOOLS like
    # every other command, satisfying the brief's allowlist verbatim.
    from app.agent_channel.registry import list_tool_specs

    return {"tools": list_tool_specs()}


Handler = Callable[[dict], dict]
