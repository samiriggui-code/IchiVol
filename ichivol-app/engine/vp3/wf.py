"""Walk-forward runner — one strategy × symbole × TF across §5 folds."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from app.agents.types import Direction
from research_lab.signals import BarSignal
from research_lab.sim import BASE_COST, CostModel, simulate

from vp2 import BAR_SECONDS, DEFAULT_SEED, INITIAL_CAPITAL
from vp2.data import bars_to_candles, build_sim_feed, load_vp1_spot
from vp3 import HTF_MAP, PROTOCOL_VERSION
from vp3.entries import entry_mask
from vp3.folds import WF_FOLDS, Fold, entry_gate_s, fold_test_window_s
from vp3.metrics import EquityMetrics, equity_metrics, trade_expectancy
from vp3.rules import strategy_rules


@dataclass
class FoldResult:
    fold_id: str
    n_trades: int
    expectancy: float | None
    sum_net: float
    equity: EquityMetrics
    exit_reasons: dict[str, int] = field(default_factory=dict)
    positive_fold: bool = False  # §5.1.9 / §9 — <5 trades ≠ positive


@dataclass
class WfReport:
    strategy: str
    symbol: str
    interval: str
    cost_profile: str
    protocol_version: str
    folds: list[FoldResult]
    aggregate_trades: int
    aggregate_expectancy: float | None
    n_positive_folds: int

    def summary(self) -> dict[str, Any]:
        return asdict(self)


def _watch_signal(t: int, sd: float | None) -> BarSignal:
    return BarSignal(t, "WATCH", Direction.NEUTRAL, sd, None, (), (), "vp3_gate", None)


def run_fold(
    strategy: str,
    *,
    symbol: str,
    interval: str,
    fold: Fold,
    root: Path | None = None,
    cost: CostModel = BASE_COST,
    seed: int = DEFAULT_SEED,
    initial: float = INITIAL_CAPITAL,
) -> FoldResult:
    rules = strategy_rules(strategy, interval)
    payload, _ = load_vp1_spot(root, symbol, interval)
    candles = bars_to_candles(payload["bars"])

    htf_interval = HTF_MAP.get(interval) if strategy in ("B5", "B6", "B7") else None
    htf_candles = None
    if htf_interval:
        htf_payload, _ = load_vp1_spot(root, symbol, htf_interval)
        htf_candles = bars_to_candles(htf_payload["bars"])

    mask = entry_mask(
        strategy,
        candles,
        htf_candles=htf_candles,
        ltf_seconds=BAR_SECONDS[interval],
        htf_seconds=BAR_SECONDS[htf_interval] if htf_interval else BAR_SECONDS["4h"],
    )
    gate = entry_gate_s(fold, interval)
    win = fold_test_window_s(fold)

    # Gate: no new entries before purge horizon into the test fold
    gated = list(mask)
    for i, c in enumerate(candles):
        if c.time < gate:
            gated[i] = False

    def decide(i: int, _c, _sd) -> str:
        return "BUY" if gated[i] else "WATCH"

    feed = build_sim_feed(candles, decide=decide)
    # Ensure gated WATCH preserves stop_distance for any stray BUY cleared above
    for t, (c, sig) in list(feed.items()):
        if t < gate and sig.decision == "BUY":
            feed[t] = (c, _watch_signal(t, sig.stop_distance))

    result = simulate({symbol: feed}, rules, cost, win, initial=initial, seed=seed)
    # §5.1.7 — trade belongs to fold of its entry bar
    trades = [t for t in result.trades if win[0] <= t.entry_time < win[1]]
    nets = [t.net for t in trades]
    reasons: dict[str, int] = {}
    for t in trades:
        reasons[t.exit_reason] = reasons.get(t.exit_reason, 0) + 1
    eq = equity_metrics(result.equity, interval=interval, equity_start=initial)
    exp = trade_expectancy(nets)
    if strategy == "B0":
        positive = eq.cagr is not None and eq.cagr > 0
    else:
        positive = len(trades) >= 5 and exp is not None and exp > 0
    return FoldResult(
        fold_id=fold.id,
        n_trades=len(trades),
        expectancy=exp,
        sum_net=sum(nets),
        equity=eq,
        exit_reasons=reasons,
        positive_fold=positive,
    )


def run_wf(
    strategy: str,
    *,
    symbol: str,
    interval: str,
    cost_profile: str = "base",
    root: Path | None = None,
    folds: tuple[Fold, ...] = WF_FOLDS,
    seed: int = DEFAULT_SEED,
) -> WfReport:
    from vp2.run import COST_PROFILES

    cost = COST_PROFILES[cost_profile]
    fold_results: list[FoldResult] = []
    for fold in folds:
        fr = run_fold(
            strategy,
            symbol=symbol,
            interval=interval,
            fold=fold,
            root=root,
            cost=cost,
            seed=seed,
        )
        fold_results.append(fr)
    agg_n = sum(f.n_trades for f in fold_results)
    agg_net = sum(f.sum_net for f in fold_results)
    return WfReport(
        strategy=strategy,
        symbol=symbol,
        interval=interval,
        cost_profile=cost_profile,
        protocol_version=PROTOCOL_VERSION,
        folds=fold_results,
        aggregate_trades=agg_n,
        aggregate_expectancy=(agg_net / agg_n) if agg_n else None,
        n_positive_folds=sum(1 for f in fold_results if f.positive_fold),
    )
