"""VP metrics §8.1 — equity bar returns, Sharpe, Sortino (all-bars downside), CAGR."""

from __future__ import annotations

import math
from dataclasses import dataclass


N_YEAR: dict[str, float] = {
    "1h": 365 * 24,  # 8760
    "4h": 365 * 6,  # 2190
    "1d": 365.0,
}


@dataclass(frozen=True)
class EquityMetrics:
    n_bars: int
    equity_start: float
    equity_end: float
    cagr: float | None
    sharpe: float | None
    sortino: float | None
    max_drawdown: float  # fraction, negative or 0
    mean_bar_return: float | None
    std_bar_return: float | None


def bar_returns_from_equity(equity_curve: list[tuple[int, float, float]]) -> list[float]:
    """Simple returns between consecutive equity marks (skip first)."""
    if len(equity_curve) < 2:
        return []
    out: list[float] = []
    for i in range(1, len(equity_curve)):
        prev = equity_curve[i - 1][1]
        cur = equity_curve[i][1]
        if prev == 0:
            out.append(0.0)
        else:
            out.append(cur / prev - 1.0)
    return out


def max_drawdown_frac(equity_curve: list[tuple[int, float, float]]) -> float:
    peak = None
    mdd = 0.0
    for _, eq, _ in equity_curve:
        peak = eq if peak is None or eq > peak else peak
        dd = eq / peak - 1.0 if peak else 0.0
        mdd = min(mdd, dd)
    return mdd


def sharpe_ratio(returns: list[float], n_year: float) -> float | None:
    """§8.1 — (mean/std) × √N_year ; rf = 0."""
    if len(returns) < 2:
        return None
    mu = sum(returns) / len(returns)
    var = sum((r - mu) ** 2 for r in returns) / (len(returns) - 1)
    if var <= 0:
        return None
    return (mu / math.sqrt(var)) * math.sqrt(n_year)


def sortino_ratio(returns: list[float], n_year: float) -> float | None:
    """§8.1 — downside_dev = sqrt(mean(min(r,0)²)) over ALL bars (zeros/positives count as 0)."""
    if not returns:
        return None
    mu = sum(returns) / len(returns)
    downside = sum(min(r, 0.0) ** 2 for r in returns) / len(returns)
    if downside <= 0:
        return None
    return (mu / math.sqrt(downside)) * math.sqrt(n_year)


def cagr(equity_start: float, equity_end: float, n_bars: int, n_year: float) -> float | None:
    """§8.1 — (eq_end/eq_start)^(N_year/n_bars) − 1."""
    if equity_start <= 0 or n_bars <= 0:
        return None
    return (equity_end / equity_start) ** (n_year / n_bars) - 1.0


def equity_metrics(
    equity_curve: list[tuple[int, float, float]],
    *,
    interval: str,
    equity_start: float | None = None,
) -> EquityMetrics:
    n_year = N_YEAR[interval]
    if not equity_curve:
        return EquityMetrics(0, 0.0, 0.0, None, None, None, 0.0, None, None)
    start = equity_start if equity_start is not None else equity_curve[0][1]
    end = equity_curve[-1][1]
    rets = bar_returns_from_equity(equity_curve)
    mu = sum(rets) / len(rets) if rets else None
    std = None
    if rets and len(rets) >= 2:
        m = sum(rets) / len(rets)
        std = math.sqrt(sum((r - m) ** 2 for r in rets) / (len(rets) - 1))
    return EquityMetrics(
        n_bars=len(equity_curve),
        equity_start=start,
        equity_end=end,
        cagr=cagr(start, end, len(equity_curve), n_year),
        sharpe=sharpe_ratio(rets, n_year),
        sortino=sortino_ratio(rets, n_year),
        max_drawdown=max_drawdown_frac(equity_curve),
        mean_bar_return=mu,
        std_bar_return=std,
    )


def trade_expectancy(nets: list[float]) -> float | None:
    if not nets:
        return None
    return sum(nets) / len(nets)
