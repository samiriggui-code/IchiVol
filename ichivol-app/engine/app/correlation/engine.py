"""Correlation matrix across a set of symbols -- CDC §6.2 "Graphe de
corrélations" (`CDC-VIZ-002`, V2 optionnel, docs/CAHIER-DES-CHARGES.md §6.2):
"Qu'est-ce qui bouge avec BTC ?" Read-only lens for Contexte/Marché, never
wired into the decision pipeline and never a vote -- same "observe, never
decide" rule as every other indicator here (docs/CAHIER-DES-CHARGES.md §8).
Explicitly *not* the Grace/GRC asset-relationship graph (§6.4): nodes are
symbols, edges are a plain statistical correlation, nothing about coverage
or "protects/monitors" topology.

Pure `statistics.correlation` (Python 3.10+, stdlib) -- this engine has no
numpy/pandas dependency (see requirements.txt) and a Pearson coefficient
over a few hundred points doesn't need one.
"""

from __future__ import annotations

import math
import statistics
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field

from app.market_data.resolve import ProviderNotWiredError, resolve_and_fetch

_MIN_OVERLAP = 20
"""Bars needed in common across two symbols for a correlation to mean
anything -- below this, report the symbol as skipped rather than a number
computed on a handful of points."""


@dataclass(frozen=True)
class SkippedSymbol:
    symbol: str
    reason: str  # "no_data_or_not_wired" | "insufficient_overlap"


@dataclass(frozen=True)
class CorrelationMatrix:
    timeframe: str
    method: str  # "log_returns" | "price"
    symbols: list[str]
    sample_size: int
    matrix: list[list[float | None]] = field(default_factory=list)
    """Symmetric, same order as `symbols`. `None` on a pair where one side
    has zero variance over the aligned window (a flat price series has no
    defined correlation, not a 0.0 one)."""
    skipped: list[SkippedSymbol] = field(default_factory=list)


def _fetch_closes(symbol: str, timeframe: str, limit: int) -> dict[int, float] | None:
    try:
        _, _, candles = resolve_and_fetch(symbol, timeframe, limit)
    except (ProviderNotWiredError, ValueError):
        return None
    if len(candles) < _MIN_OVERLAP:
        return None
    return {c.time: c.close for c in candles}


def _series_for(method: str, closes_by_time: dict[int, float], aligned_times: list[int]) -> list[float]:
    prices = [closes_by_time[t] for t in aligned_times]
    if method == "price":
        return prices
    # log returns: bar-to-bar, one shorter than `prices` -- every symbol
    # walks the same `aligned_times` index so return series line up pair by
    # pair regardless of which symbols dropped out earlier.
    return [math.log(prices[i + 1] / prices[i]) for i in range(len(prices) - 1)]


def _safe_correlation(a: list[float], b: list[float]) -> float | None:
    try:
        return statistics.correlation(a, b)
    except statistics.StatisticsError:
        return None  # zero variance on one side -- undefined, not 0.0


def compute_correlation_matrix(
    symbols: list[str],
    *,
    timeframe: str = "1h",
    limit: int = 300,
    method: str = "log_returns",
    concurrency: int = 6,
) -> CorrelationMatrix:
    if method not in ("log_returns", "price"):
        raise ValueError(f"invalid_method: {method!r} (expected 'log_returns' or 'price')")

    closes_by_symbol: dict[str, dict[int, float]] = {}
    skipped: list[SkippedSymbol] = []
    with ThreadPoolExecutor(max_workers=max(1, concurrency)) as pool:
        futures = {pool.submit(_fetch_closes, s, timeframe, limit): s for s in symbols}
        for future in as_completed(futures):
            symbol = futures[future]
            result = future.result()
            if result is None:
                skipped.append(SkippedSymbol(symbol=symbol, reason="no_data_or_not_wired"))
            else:
                closes_by_symbol[symbol] = result

    # Preserve the caller's requested order, not ThreadPoolExecutor completion order.
    ordered_symbols = [s for s in symbols if s in closes_by_symbol]

    if len(ordered_symbols) < 2:
        return CorrelationMatrix(
            timeframe=timeframe,
            method=method,
            symbols=ordered_symbols,
            sample_size=0,
            matrix=[[1.0]] if len(ordered_symbols) == 1 else [],
            skipped=skipped,
        )

    aligned_times = sorted(
        set.intersection(*(set(closes_by_symbol[s].keys()) for s in ordered_symbols))
    )

    if len(aligned_times) < _MIN_OVERLAP:
        # Different providers close their bars on different clocks
        # (biquote vs. Binance Vision) -- too little overlap means no
        # honest matrix, not a matrix computed on a handful of points.
        return CorrelationMatrix(
            timeframe=timeframe,
            method=method,
            symbols=[],
            sample_size=len(aligned_times),
            matrix=[],
            skipped=skipped
            + [SkippedSymbol(symbol=s, reason="insufficient_overlap") for s in ordered_symbols],
        )

    series = {s: _series_for(method, closes_by_symbol[s], aligned_times) for s in ordered_symbols}
    sample_size = len(next(iter(series.values())))

    matrix = [
        [1.0 if a == b else _safe_correlation(series[a], series[b]) for b in ordered_symbols]
        for a in ordered_symbols
    ]

    return CorrelationMatrix(
        timeframe=timeframe,
        method=method,
        symbols=ordered_symbols,
        sample_size=sample_size,
        matrix=matrix,
        skipped=skipped,
    )
