"""VP2 run wrapper — reproducible metadata around research_lab.sim.simulate."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from research_lab.sim import ADVERSE_COST, BASE_COST, CostModel, RunResult, simulate

from vp2 import DEFAULT_SEED, INITIAL_CAPITAL, PROTOCOL_ID, PROTOCOL_VERSION
from vp2.data import DecisionFn, build_sim_feed, bars_to_candles, load_vp1_spot, window_seconds
from vp2.rules import common_rules

COST_PROFILES: dict[str, CostModel] = {
    "base": BASE_COST,
    "adverse": ADVERSE_COST,
}


@dataclass
class Vp2RunMeta:
    protocol: str
    protocol_version: str
    symbol: str
    interval: str
    cost_profile: str
    seed: int
    initial_capital: float
    data_sha256: str
    data_rel: str
    window: tuple[int, int]
    rules_name: str
    exit_mode: str
    time_stop_bars: int | None
    full_cash: bool
    allow_short: bool
    immediate_fill: bool
    n_bars: int
    n_trades: int
    cash_end: float
    exit_reasons: dict[str, int] = field(default_factory=dict)


@dataclass
class Vp2Run:
    meta: Vp2RunMeta
    result: RunResult

    def summary(self) -> dict[str, Any]:
        m = asdict(self.meta)
        m["ledger_ok"] = self.result.ledger_diff == {} or all(
            abs(float(v)) < 1e-6 for v in self.result.ledger_diff.values()
        )
        return m


def _exit_reasons(result: RunResult) -> dict[str, int]:
    out: dict[str, int] = {}
    for t in result.trades:
        out[t.exit_reason] = out.get(t.exit_reason, 0) + 1
    return out


def run_common(
    *,
    symbol: str,
    interval: str,
    cost_profile: str = "base",
    seed: int = DEFAULT_SEED,
    root: Path | None = None,
    decide: DecisionFn | None = None,
    window: tuple[str, str] | None = None,
    initial: float = INITIAL_CAPITAL,
) -> Vp2Run:
    """Execute one VP2 harness run on frozen VP1 spot data.

    ``decide`` injects entries (default: no entries). VP3 supplies B* entry rules.
    """
    if cost_profile not in COST_PROFILES:
        raise ValueError(f"cost_profile must be one of {sorted(COST_PROFILES)}")
    cost = COST_PROFILES[cost_profile]
    rules = common_rules(interval)
    if rules.immediate_fill:
        raise RuntimeError("VP §1ter forbids immediate_fill")

    payload, digest = load_vp1_spot(root, symbol, interval)
    candles = bars_to_candles(payload["bars"])
    feed = build_sim_feed(candles, decide=decide)
    data = {symbol: feed}

    if window is None:
        win = window_seconds("2020-09-01", "2026-08-31", interval)
    else:
        win = window_seconds(window[0], window[1], interval)

    result = simulate(data, rules, cost, win, initial=initial, seed=seed)
    from vp2.data import series_rel_path

    meta = Vp2RunMeta(
        protocol=PROTOCOL_ID,
        protocol_version=PROTOCOL_VERSION,
        symbol=symbol,
        interval=interval,
        cost_profile=cost_profile,
        seed=seed,
        initial_capital=initial,
        data_sha256=digest,
        data_rel=series_rel_path(symbol, interval),
        window=win,
        rules_name=rules.name,
        exit_mode=rules.exit_mode,
        time_stop_bars=rules.time_stop_bars,
        full_cash=rules.full_cash,
        allow_short=rules.allow_short,
        immediate_fill=rules.immediate_fill,
        n_bars=len(candles),
        n_trades=len(result.trades),
        cash_end=result.cash_end,
        exit_reasons=_exit_reasons(result),
    )
    return Vp2Run(meta=meta, result=result)


def run_from_feed(
    data: dict[str, dict[int, tuple]],
    *,
    interval: str,
    cost_profile: str = "base",
    seed: int = DEFAULT_SEED,
    window: tuple[int, int],
    initial: float = INITIAL_CAPITAL,
    data_sha256: str = "synthetic",
    data_rel: str = "synthetic",
    symbol: str | None = None,
) -> Vp2Run:
    """Unit-test / synthetic path — same rules & metadata shape, no VP1 disk."""
    cost = COST_PROFILES[cost_profile]
    rules = common_rules(interval)
    result = simulate(data, rules, cost, window, initial=initial, seed=seed)
    sym = symbol or sorted(data)[0]
    meta = Vp2RunMeta(
        protocol=PROTOCOL_ID,
        protocol_version=PROTOCOL_VERSION,
        symbol=sym,
        interval=interval,
        cost_profile=cost_profile,
        seed=seed,
        initial_capital=initial,
        data_sha256=data_sha256,
        data_rel=data_rel,
        window=window,
        rules_name=rules.name,
        exit_mode=rules.exit_mode,
        time_stop_bars=rules.time_stop_bars,
        full_cash=rules.full_cash,
        allow_short=rules.allow_short,
        immediate_fill=rules.immediate_fill,
        n_bars=sum(len(v) for v in data.values()),
        n_trades=len(result.trades),
        cash_end=result.cash_end,
        exit_reasons=_exit_reasons(result),
    )
    return Vp2Run(meta=meta, result=result)
