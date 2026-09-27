"""P3 — BUY event study against same-symbol same-month controls (amendement VP0-2026-09-28 Q.5).

Primary event = start of a BUY series. Return = close(t+h) / open(t+1) − 1 (entry at the next open, like the paper).
Controls = 20 bars drawn without replacement in the same symbol and calendar month (UTC), eligible, full window,
event bar excluded. Interval = bootstrap over calendar months (whole months, all assets), 10 000 draws, seed 7;
decision at the Bonferroni level 98.75 % (4 horizons), 95 % reported for information.
"""

from __future__ import annotations

import random
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from app.indicators.ichimoku import Candle
from research_lab.signals import BarSignal
from research_lab.sim import CostModel

from vpp import LIVE_WINDOW_BARS, SEED
from vpp.diagnose import month_cluster_ci

HORIZONS = (24, 48, 96, 168)
N_CONTROLS = 20
LEVEL_DECISION = 1 - 0.05 / len(HORIZONS)  # 0.9875
LEVEL_INFO = 0.95


def _month(t: int) -> str:
    return datetime.fromtimestamp(t, timezone.utc).strftime("%Y-%m")


def _ret(c: list[Candle], t_idx: int, h: int) -> float | None:
    """Entry at open(t+1), exit at close(t+h); None if the window leaves the data."""
    if t_idx + h >= len(c):
        return None
    return c[t_idx + h].close / c[t_idx + 1].open - 1.0


def events(sigs: dict[str, list[BarSignal]], candles: dict[str, list[Candle]], window, kind: str) -> list[tuple[str, int]]:
    out = []
    for s in sorted(sigs):
        c, ss = candles[s], sigs[s]
        for i in range(LIVE_WINDOW_BARS - 1, len(ss)):
            if not (window[0] <= c[i].time < window[1]) or ss[i].decision != "BUY":
                continue
            if kind == "series_start" and i > 0 and ss[i - 1].decision == "BUY":
                continue
            out.append((s, i))
    return out


def study(
    ev: list[tuple[str, int]], candles: dict[str, list[Candle]], window, costs: dict[str, CostModel],
    costs_adv: dict[str, CostModel], *, with_ci: bool = True,
) -> dict[str, Any]:
    rng = random.Random(SEED)
    # eligible bars per (symbol, month), by horizon feasibility checked at draw time
    pool: dict[tuple[str, str], list[int]] = defaultdict(list)
    for s, c in candles.items():
        for i in range(LIVE_WINDOW_BARS - 1, len(c)):
            if window[0] <= c[i].time < window[1]:
                pool[(s, _month(c[i].time))].append(i)
    rows: dict[int, list[dict[str, Any]]] = {h: [] for h in HORIZONS}
    for s, i in ev:
        c = candles[s]
        m = _month(c[i].time)
        cand = [j for j in pool[(s, m)] if j != i]
        rt = 2 * (costs[s].commission_bps + costs[s].spread_bps + costs[s].slippage_bps) / 1e4
        rt_adv = 2 * (costs_adv[s].commission_bps + costs_adv[s].spread_bps + costs_adv[s].slippage_bps) / 1e4
        for h in HORIZONS:
            r = _ret(c, i, h)
            if r is None:
                continue
            feasible = [j for j in cand if j + h < len(c)]
            if len(feasible) < N_CONTROLS:
                continue
            ctrl = [_ret(c, j, h) for j in rng.sample(feasible, N_CONTROLS)]
            cm = sum(ctrl) / len(ctrl)
            rows[h].append({"symbol": s, "month": m, "year": m[:4], "r": r, "ctrl": cm, "d": r - cm,
                            "net": r - rt, "net_adv": r - rt_adv, "cost_rt": rt})
    out: dict[str, Any] = {}
    for h in HORIZONS:
        g = rows[h]
        res: dict[str, Any] = {"n": len(g)}
        if not g:
            out[str(h)] = res
            continue
        pct = lambda x: 100 * x  # noqa: E731
        for key in ("r", "ctrl", "d", "net", "net_adv"):
            vals = sorted(x[key] for x in g)
            res[key] = {"mean_pct": pct(sum(vals) / len(vals)), "median_pct": pct(vals[len(vals) // 2]),
                        "share_positive_pct": 100 * sum(1 for v in vals if v > 0) / len(vals)}
            if with_ci and key in ("r", "ctrl", "d", "net", "net_adv"):
                for lvl, tag in ((LEVEL_DECISION, "ci_decision"), (LEVEL_INFO, "ci_95")):
                    ci = month_cluster_ci([(x["month"], x[key]) for x in g], level=lvl)
                    res[key][tag] = {"lo_pct": pct(ci["lo"]), "hi_pct": pct(ci["hi"]), "level": lvl,
                                     "months": ci["months"]}
        res["mean_cost_rt_pct"] = pct(sum(x["cost_rt"] for x in g) / len(g))
        if with_ci:
            res["A_surperformance"] = res["d"]["ci_decision"]["lo_pct"] > 0
            res["B_net_paper"] = res["net"]["ci_decision"]["lo_pct"] > 0
            res["favorable"] = res["A_surperformance"] and res["B_net_paper"]
            res["excluded_mean_advantage_above_pct"] = res["d"]["ci_decision"]["hi_pct"]
        by_year: dict[str, list] = defaultdict(list)
        by_sym: dict[str, list] = defaultdict(list)
        for x in g:
            by_year[x["year"]].append(x)
            by_sym[x["symbol"]].append(x)
        desc = lambda xs: {"n": len(xs), "r_mean_pct": pct(sum(x["r"] for x in xs) / len(xs)),  # noqa: E731
                           "d_mean_pct": pct(sum(x["d"] for x in xs) / len(xs))}
        res["by_year"] = {k: desc(v) for k, v in sorted(by_year.items())}
        res["by_symbol"] = {k: desc(v) for k, v in sorted(by_sym.items())}
        out[str(h)] = res
    return out


def run(sigs, candles, window, costs, costs_adv, r1_trades: list | None = None) -> dict[str, Any]:
    """``r1_trades``: research_lab.sim.Trade objects of R1 (secondary 'executed entries' event set)."""
    primary = events(sigs, candles, window, "series_start")
    every = events(sigs, candles, window, "all")
    out = {
        "method": {"horizons": HORIZONS, "controls": N_CONTROLS, "level_decision": LEVEL_DECISION,
                   "level_info": LEVEL_INFO, "seed": SEED, "bootstrap": "calendar-month clusters, 10000"},
        "primary_series_start": {"n_events": len(primary), **study(primary, candles, window, costs, costs_adv)},
        "secondary_all_buy_bars": {"n_events": len(every), **study(every, candles, window, costs, costs_adv)},
    }
    if r1_trades is not None:
        idx = {s: {c.time: i for i, c in enumerate(candles[s])} for s in candles}
        # executed entries: the event bar is the signal bar (entry at its next open)
        executed = [(t.symbol, idx[t.symbol][t.signal_time]) for t in r1_trades]
        out["secondary_r1_executed"] = {"n_events": len(executed),
                                        **study(executed, candles, window, costs, costs_adv)}
    horizons = out["primary_series_start"]
    fav = [int(h) for h in map(str, HORIZONS) if horizons.get(h, {}).get("favorable")]
    out["decision"] = {
        "favorable_horizons": fav,
        "shortest_favorable": min(fav) if fav else None,
        "suspend_entry_optimisation": not fav,
    }
    return out
