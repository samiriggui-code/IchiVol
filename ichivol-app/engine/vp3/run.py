"""Run VP3 strategy Bi on frozen VP1 data via VP2 harness."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from research_lab.sim import ADVERSE_COST, BASE_COST, CostModel, RunResult, simulate

from vp2 import BAR_SECONDS, DEFAULT_SEED, INITIAL_CAPITAL
from vp2.data import bars_to_candles, build_sim_feed, load_vp1_spot, series_rel_path, window_seconds
from vp3 import HTF_MAP, PROTOCOL_ID, PROTOCOL_VERSION, STRATEGIES
from vp3.entries import decisions_from_mask, entry_mask
from vp3.rules import strategy_rules

COST_PROFILES: dict[str, CostModel] = {"base": BASE_COST, "adverse": ADVERSE_COST}


@dataclass
class Vp3RunMeta:
    protocol: str
    protocol_version: str
    strategy: str
    symbol: str
    interval: str
    htf_interval: str | None
    cost_profile: str
    seed: int
    initial_capital: float
    data_sha256: str
    htf_sha256: str | None
    data_rel: str
    window: tuple[int, int]
    rules_name: str
    exit_mode: str
    n_trades: int
    cash_end: float
    exit_reasons: dict[str, int] = field(default_factory=dict)
    n_entry_signals: int = 0


@dataclass
class Vp3Run:
    meta: Vp3RunMeta
    result: RunResult

    def summary(self) -> dict[str, Any]:
        return asdict(self.meta)


def run_strategy(
    strategy: str,
    *,
    symbol: str,
    interval: str,
    cost_profile: str = "base",
    seed: int = DEFAULT_SEED,
    root: Path | None = None,
    window: tuple[str, str] | None = None,
    initial: float = INITIAL_CAPITAL,
) -> Vp3Run:
    if strategy not in STRATEGIES:
        raise ValueError(f"strategy must be one of {STRATEGIES}")
    if cost_profile not in COST_PROFILES:
        raise ValueError(f"cost_profile must be one of {sorted(COST_PROFILES)}")
    if interval not in BAR_SECONDS:
        raise ValueError(interval)

    rules = strategy_rules(strategy, interval)
    cost = COST_PROFILES[cost_profile]
    payload, digest = load_vp1_spot(root, symbol, interval)
    candles = bars_to_candles(payload["bars"])

    htf_interval = HTF_MAP.get(interval) if strategy in ("B5", "B6", "B7") else None
    htf_candles = None
    htf_digest = None
    if htf_interval:
        htf_payload, htf_digest = load_vp1_spot(root, symbol, htf_interval)
        htf_candles = bars_to_candles(htf_payload["bars"])

    mask = entry_mask(
        strategy,
        candles,
        htf_candles=htf_candles,
        ltf_seconds=BAR_SECONDS[interval],
        htf_seconds=BAR_SECONDS[htf_interval] if htf_interval else BAR_SECONDS["4h"],
    )
    decisions = decisions_from_mask(mask)
    # Capture decisions in a closure for build_sim_feed
    dec_by_i = decisions

    def decide(i: int, _c, _sd) -> str:
        return dec_by_i[i] if i < len(dec_by_i) else "WATCH"

    feed = build_sim_feed(candles, decide=decide)
    if window is None:
        win = window_seconds("2020-09-01", "2026-08-31", interval)
    else:
        win = window_seconds(window[0], window[1], interval)

    result = simulate({symbol: feed}, rules, cost, win, initial=initial, seed=seed)
    reasons: dict[str, int] = {}
    for t in result.trades:
        reasons[t.exit_reason] = reasons.get(t.exit_reason, 0) + 1

    meta = Vp3RunMeta(
        protocol=PROTOCOL_ID,
        protocol_version=PROTOCOL_VERSION,
        strategy=strategy,
        symbol=symbol,
        interval=interval,
        htf_interval=htf_interval,
        cost_profile=cost_profile,
        seed=seed,
        initial_capital=initial,
        data_sha256=digest,
        htf_sha256=htf_digest,
        data_rel=series_rel_path(symbol, interval),
        window=win,
        rules_name=rules.name,
        exit_mode=rules.exit_mode,
        n_trades=len(result.trades),
        cash_end=result.cash_end,
        exit_reasons=reasons,
        n_entry_signals=sum(1 for m in mask if m),
    )
    return Vp3Run(meta=meta, result=result)
