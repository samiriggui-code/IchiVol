"""T7 — Monte Carlo / risk-of-ruin on trade returns (research-only).

Bootstrap-resamples **net** trade simple returns into equity paths.
Never changes strategy, fills, or live gates. Requires enough trades
(``min_trades``) before reporting; otherwise returns an empty/insufficient report.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Sequence

MONTE_CARLO_VERSION = "monte_carlo_v0"
DEFAULT_MIN_TRADES = 20
DEFAULT_N_PATHS = 1000
DEFAULT_RUIN_FLOOR = 0.50  # equity ≤ 50% of start ⇒ ruin


@dataclass(frozen=True)
class MonteCarloReport:
    version: str
    n_trades: int
    n_paths: int
    seed: int
    ruin_floor: float
    min_trades: int
    sufficient: bool
    mean_final_equity: float | None = None
    p05_final_equity: float | None = None
    p50_final_equity: float | None = None
    p95_final_equity: float | None = None
    mean_max_drawdown: float | None = None
    p95_max_drawdown: float | None = None
    risk_of_ruin: float | None = None
    """Fraction of paths that touched equity ≤ ruin_floor."""
    sample_final_equities: list[float] = field(default_factory=list)
    disclaimer: str = (
        "Monte Carlo on historical trade returns — research only; "
        "does not alter strategy, fills, or live gates."
    )

    def to_dict(self) -> dict:
        return {
            "version": self.version,
            "n_trades": self.n_trades,
            "n_paths": self.n_paths,
            "seed": self.seed,
            "ruin_floor": self.ruin_floor,
            "min_trades": self.min_trades,
            "sufficient": self.sufficient,
            "mean_final_equity": self.mean_final_equity,
            "p05_final_equity": self.p05_final_equity,
            "p50_final_equity": self.p50_final_equity,
            "p95_final_equity": self.p95_final_equity,
            "mean_max_drawdown": self.mean_max_drawdown,
            "p95_max_drawdown": self.p95_max_drawdown,
            "risk_of_ruin": self.risk_of_ruin,
            "sample_final_equities": list(self.sample_final_equities),
            "disclaimer": self.disclaimer,
        }


def _percentile(sorted_vals: list[float], q: float) -> float:
    """Linear interpolation percentile; ``sorted_vals`` non-empty, q in [0,1]."""
    if not sorted_vals:
        raise ValueError("empty")
    if len(sorted_vals) == 1:
        return sorted_vals[0]
    pos = q * (len(sorted_vals) - 1)
    lo = int(math.floor(pos))
    hi = int(math.ceil(pos))
    if lo == hi:
        return sorted_vals[lo]
    w = pos - lo
    return sorted_vals[lo] * (1.0 - w) + sorted_vals[hi] * w


def _path_stats(
    returns: Sequence[float],
    *,
    ruin_floor: float,
) -> tuple[float, float, bool]:
    """Returns (final_equity, max_drawdown, hit_ruin)."""
    equity = 1.0
    peak = 1.0
    max_dd = 0.0
    hit_ruin = False
    for r in returns:
        equity *= 1.0 + float(r)
        if equity <= 0:
            equity = 0.0
            hit_ruin = True
            max_dd = 1.0
            break
        peak = max(peak, equity)
        dd = (peak - equity) / peak if peak > 0 else 0.0
        max_dd = max(max_dd, dd)
        if equity <= ruin_floor:
            hit_ruin = True
    return equity, max_dd, hit_ruin


def run_monte_carlo(
    trade_net_returns: Sequence[float],
    *,
    n_paths: int = DEFAULT_N_PATHS,
    seed: int = 42,
    ruin_floor: float = DEFAULT_RUIN_FLOOR,
    min_trades: int = DEFAULT_MIN_TRADES,
    sample_limit: int = 20,
) -> MonteCarloReport:
    """Bootstrap Monte Carlo on net simple returns (e.g. exp(net_log)-1)."""
    n = len(trade_net_returns)
    if n < min_trades or n == 0:
        return MonteCarloReport(
            version=MONTE_CARLO_VERSION,
            n_trades=n,
            n_paths=n_paths,
            seed=seed,
            ruin_floor=ruin_floor,
            min_trades=min_trades,
            sufficient=False,
        )

    rng = random.Random(seed)
    rets = [float(r) for r in trade_net_returns]
    finals: list[float] = []
    dds: list[float] = []
    ruins = 0
    for _ in range(n_paths):
        path = [rets[rng.randrange(n)] for _ in range(n)]
        final, dd, hit = _path_stats(path, ruin_floor=ruin_floor)
        finals.append(final)
        dds.append(dd)
        if hit:
            ruins += 1

    finals_sorted = sorted(finals)
    dds_sorted = sorted(dds)
    return MonteCarloReport(
        version=MONTE_CARLO_VERSION,
        n_trades=n,
        n_paths=n_paths,
        seed=seed,
        ruin_floor=ruin_floor,
        min_trades=min_trades,
        sufficient=True,
        mean_final_equity=sum(finals) / len(finals),
        p05_final_equity=_percentile(finals_sorted, 0.05),
        p50_final_equity=_percentile(finals_sorted, 0.50),
        p95_final_equity=_percentile(finals_sorted, 0.95),
        mean_max_drawdown=sum(dds) / len(dds),
        p95_max_drawdown=_percentile(dds_sorted, 0.95),
        risk_of_ruin=ruins / n_paths,
        sample_final_equities=finals[:sample_limit],
    )
