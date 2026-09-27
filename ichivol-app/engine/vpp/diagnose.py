"""VP-P measures and diagnostic (amendement VP0-2026-09-27b §P.3–P.4). Pure functions of a RunResult + data.

Every definition below is the pre-registered one; thresholds are module constants, never tuned.
Post-decision prices are used only to DESCRIBE what happened (F1–F5, post-exit), never to build a rule.
"""

from __future__ import annotations

import bisect
import statistics
from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any, Iterable

from app.indicators.ichimoku import Candle
from research_lab.signals import BarSignal
from research_lab.sim import RunResult, Trade

from vpp import FOLDS, LIVE_WINDOW_BARS

N_YEAR_1H = 8760
FWD_H = (1, 4, 12, 24, 48)
POST_EXIT_H = 24
RUNUP_H = (12, 24)
F1_MFE_MAX = 0.5
F2_MFE_MIN = 1.0
F34_MOVE_R = 1.0


def _iso(t: int) -> str:
    return datetime.fromtimestamp(t, timezone.utc).strftime("%Y-%m-%d %H:%M")


def fold_windows() -> list[tuple[str, int, int]]:
    out = []
    for name, a, b in FOLDS:
        s = int(datetime.fromisoformat(a).replace(tzinfo=timezone.utc).timestamp())
        e = int(datetime.fromisoformat(b).replace(tzinfo=timezone.utc).timestamp()) + 86400
        out.append((name, s, e))
    return out


def fold_of(t: int) -> str | None:
    for name, s, e in fold_windows():
        if s <= t < e:
            return name
    return None


def _mean(xs: Iterable[float]) -> float | None:
    xs = list(xs)
    return statistics.fmean(xs) if xs else None


def _median(xs: Iterable[float]) -> float | None:
    xs = list(xs)
    return statistics.median(xs) if xs else None


def _terciles(values: list[float]) -> tuple[float, float] | None:
    v = sorted(x for x in values if x is not None)
    if len(v) < 3:
        return None
    return v[len(v) // 3], v[2 * len(v) // 3]


def _bucket(x: float | None, cuts: tuple[float, float] | None) -> str:
    if x is None or cuts is None:
        return "n/a"
    return "bas" if x < cuts[0] else ("moyen" if x < cuts[1] else "haut")


def max_drawdown(curve: list[tuple[int, float]]) -> dict[str, Any]:
    peak, peak_t, worst, worst_t, worst_peak_t = -1.0, None, 0.0, None, None
    for t, eq in curve:
        if eq > peak:
            peak, peak_t = eq, t
        dd = eq / peak - 1.0 if peak > 0 else 0.0
        if dd < worst:
            worst, worst_t, worst_peak_t = dd, t, peak_t
    return {
        "max_dd_pct": 100 * worst,
        "peak_at": _iso(worst_peak_t) if worst_peak_t else None,
        "trough_at": _iso(worst_t) if worst_t else None,
    }


# --- per-trade diagnostic rows ------------------------------------------------------------------------------------

class SeriesIndex:
    """Fast time → index lookup on one symbol's 1h candles."""

    def __init__(self, candles: list[Candle]):
        self.c = candles
        self.t = [c.time for c in candles]

    def idx(self, t: int) -> int | None:
        i = bisect.bisect_left(self.t, t)
        return i if i < len(self.t) and self.t[i] == t else None


def trade_rows(
    trades: list[Trade], series: dict[str, SeriesIndex], sigs: dict[str, dict[int, BarSignal]],
) -> list[dict[str, Any]]:
    rows = []
    for tr in trades:
        s = series[tr.symbol]
        c = s.c
        sd = tr.entry_fill - tr.stop_level  # stop distance (R in price), levels anchored on the fill
        e = s.idx(tr.entry_time)
        x = s.idx(tr.exit_time)
        si = s.idx(tr.signal_time)
        sig = sigs[tr.symbol].get(tr.signal_time)
        mfe_r = max(0.0, (tr.high_seen - tr.entry_fill) / sd)
        mae_r = max(0.0, (tr.entry_fill - tr.low_seen) / sd)
        gross_r = (tr.exit_raw - tr.entry_raw) / sd
        net_r = tr.net / tr.risk_amount if tr.risk_amount else 0.0
        fwd = {}
        for h in FWD_H:
            j = e + h - 1
            if j < len(c):
                fwd[h] = {"pct": 100 * (c[j].close / tr.entry_raw - 1), "r": (c[j].close - tr.entry_raw) / sd}
        runup = {}
        for h in RUNUP_H:
            if si is not None and si - h >= 0:
                runup[h] = (c[si].close - c[si - h].close) / sd
        stop_exit = tr.exit_reason.startswith("stop")
        intrabar = tr.exit_reason.startswith(("stop", "take_profit"))
        # post-exit window: the H bars after the exit instant (an intrabar exit skips the rest of its bar)
        a = x + 1 if intrabar else x
        post = c[a: a + POST_EXIT_H]
        post_high = max((b.high for b in post), default=None)
        post_close = post[-1].close if len(post) == POST_EXIT_H else None
        hold_h = (tr.exit_time - tr.entry_time) / 3600
        rows.append({
            "symbol": tr.symbol,
            "fold": fold_of(tr.entry_time),
            "year": datetime.fromtimestamp(tr.entry_time, timezone.utc).year,
            "entry": _iso(tr.entry_time),
            "exit": _iso(tr.exit_time),
            "exit_reason": tr.exit_reason,
            "hold_h": hold_h,
            "notional": tr.notional,
            "risk_amount": tr.risk_amount,
            "gross": tr.gross,
            "commission": tr.commission,
            "friction": tr.friction_cost,
            "net": tr.net,
            "net_r": net_r,
            "gross_r": gross_r,
            "mfe_r": mfe_r,
            "mae_r": mae_r,
            "capture": gross_r / mfe_r if mfe_r > 0 else None,
            "fwd": fwd,
            "runup": runup,
            "mtf_aligned": None if sig is None else sig.mtf_aligned,
            "rvol": None if sig is None else sig.rvol,
            "post_high_r_vs_exit": None if post_high is None else (post_high - tr.exit_raw) / sd,
            "post_close_r_vs_exit": None if post_close is None else (post_close - tr.exit_raw) / sd,
            "F1_entry_adverse": mfe_r < F1_MFE_MAX,
            "F2_gave_back": mfe_r >= F2_MFE_MIN and tr.gross <= 0,
            "F3_exit_then_continued": (not stop_exit) and post_high is not None
                                      and post_high >= tr.exit_raw + F34_MOVE_R * sd,
            "F4_stop_then_rebound": stop_exit and post_high is not None
                                    and post_high >= tr.entry_raw + F34_MOVE_R * sd,
            "F5_gross_pos_net_neg": tr.gross > 0 and tr.net <= 0,
        })
    return rows


# --- aggregates ---------------------------------------------------------------------------------------------------

def trade_stats(rows: list[dict[str, Any]]) -> dict[str, Any]:
    n = len(rows)
    if n == 0:
        return {"n": 0}
    wins = [r for r in rows if r["net"] > 0]
    losses = [r for r in rows if r["net"] <= 0]
    gross = sum(r["gross"] for r in rows)
    comm = sum(r["commission"] for r in rows)
    fric = sum(r["friction"] for r in rows)
    return {
        "n": n,
        "net_sum": sum(r["net"] for r in rows),
        "gross_sum": gross,
        "commission_sum": comm,
        "friction_sum": fric,
        "win_rate_pct": 100 * len(wins) / n,
        "avg_win": _mean(r["net"] for r in wins),
        "avg_loss": _mean(r["net"] for r in losses),
        "expectancy_eur": _mean(r["net"] for r in rows),
        "expectancy_r": _mean(r["net_r"] for r in rows),
        "expectancy_pct_notional": _mean(100 * r["net"] / r["notional"] for r in rows),
        "gross_expectancy_pct_notional": _mean(100 * r["gross"] / r["notional"] for r in rows),
        "cost_per_trade_pct_notional": _mean(100 * (r["commission"] + r["friction"]) / r["notional"] for r in rows),
        "hold_h_mean": _mean(r["hold_h"] for r in rows),
        "hold_h_median": _median(r["hold_h"] for r in rows),
        "avg_notional": _mean(r["notional"] for r in rows),
        "avg_risk_amount": _mean(r["risk_amount"] for r in rows),
        "mfe_r_mean": _mean(r["mfe_r"] for r in rows),
        "mae_r_mean": _mean(r["mae_r"] for r in rows),
        "gross_r_mean": _mean(r["gross_r"] for r in rows),
    }


def group_stats(rows: list[dict[str, Any]], key: str) -> dict[str, Any]:
    groups: dict[Any, list] = defaultdict(list)
    for r in rows:
        groups[r[key]].append(r)
    out = {}
    for k in sorted(groups, key=lambda v: str(v)):
        g = groups[k]
        out[str(k)] = {
            "n": len(g),
            "net_sum": sum(r["net"] for r in g),
            "win_rate_pct": 100 * sum(1 for r in g if r["net"] > 0) / len(g),
            "expectancy_eur": _mean(r["net"] for r in g),
            "expectancy_r": _mean(r["net_r"] for r in g),
            "mfe_r_mean": _mean(r["mfe_r"] for r in g),
            "hold_h_mean": _mean(r["hold_h"] for r in g),
        }
    return out


def flag_stats(rows: list[dict[str, Any]]) -> dict[str, Any]:
    out = {}
    for f in ("F1_entry_adverse", "F2_gave_back", "F3_exit_then_continued", "F4_stop_then_rebound",
              "F5_gross_pos_net_neg"):
        g = [r for r in rows if r[f]]
        out[f] = {"n": len(g), "pct_trades": 100 * len(g) / len(rows) if rows else None,
                  "net_sum": sum(r["net"] for r in g), "expectancy_r": _mean(r["net_r"] for r in g)}
    stops = [r for r in rows if r["exit_reason"].startswith("stop")]
    non_stops = [r for r in rows if not r["exit_reason"].startswith("stop")]
    out["_bases"] = {"stops": len(stops), "non_stop_exits": len(non_stops)}
    return out


def exit_quality(rows: list[dict[str, Any]]) -> dict[str, Any]:
    with_mfe = [r for r in rows if r["mfe_r"] > 0]
    winners = [r for r in rows if r["gross"] > 0]
    return {
        "capture_all_ratio_of_sums": (sum(r["gross_r"] for r in with_mfe) / sum(r["mfe_r"] for r in with_mfe))
        if with_mfe else None,
        "capture_winners_median": _median(r["capture"] for r in winners if r["capture"] is not None),
        "mfe_r_quantiles": _quantiles([r["mfe_r"] for r in rows]),
        "mae_r_quantiles": _quantiles([r["mae_r"] for r in rows]),
        "share_reaching_1r_pct": 100 * sum(1 for r in rows if r["mfe_r"] >= 1) / len(rows) if rows else None,
        "share_reaching_2r_pct": 100 * sum(1 for r in rows if r["mfe_r"] >= 2) / len(rows) if rows else None,
        "post_exit_by_reason": {
            reason: {
                "n": len(g),
                "post_high_r_mean": _mean(r["post_high_r_vs_exit"] for r in g if r["post_high_r_vs_exit"] is not None),
                "post_close_r_mean": _mean(r["post_close_r_vs_exit"] for r in g
                                           if r["post_close_r_vs_exit"] is not None),
            }
            for reason, g in _by(rows, "exit_reason").items()
        },
    }


def _by(rows, key):
    d: dict[Any, list] = defaultdict(list)
    for r in rows:
        d[r[key]].append(r)
    return dict(d)


def _quantiles(xs: list[float]) -> dict[str, float] | None:
    v = sorted(xs)
    if not v:
        return None
    q = lambda p: v[min(len(v) - 1, int(p * len(v)))]  # noqa: E731
    return {"p10": q(0.1), "p25": q(0.25), "p50": q(0.5), "p75": q(0.75), "p90": q(0.9)}


def entry_timing(rows, series: dict[str, SeriesIndex], window: tuple[int, int]) -> dict[str, Any]:
    """Forward returns after entry vs the unconditional drift of the same symbols (eligible bars in window)."""
    drift: dict[int, list[float]] = defaultdict(list)
    drift_pos: dict[int, list[int]] = defaultdict(list)
    weights = Counter(r["symbol"] for r in rows)
    per_sym_drift: dict[str, dict[int, float]] = {}
    for sym in weights:
        c = series[sym].c
        acc: dict[int, list[float]] = defaultdict(list)
        for i in range(LIVE_WINDOW_BARS - 1, len(c)):
            if not (window[0] <= c[i].time < window[1]):
                continue
            for h in FWD_H:
                j = i + h - 1
                if j < len(c):
                    acc[h].append(100 * (c[j].close / c[i].open - 1))
        per_sym_drift[sym] = {h: _mean(v) for h, v in acc.items()}
        for h, v in acc.items():
            drift_pos[h].append(sum(1 for x in v if x > 0) / len(v))
    out = {}
    for h in FWD_H:
        got = [r["fwd"][h] for r in rows if h in r["fwd"]]
        # drift weighted like the trades (same symbol mix)
        base = _mean(per_sym_drift[r["symbol"]][h] for r in rows if h in r["fwd"])
        out[str(h)] = {
            "n": len(got),
            "mean_pct": _mean(g["pct"] for g in got),
            "median_pct": _median(g["pct"] for g in got),
            "mean_r": _mean(g["r"] for g in got),
            "share_positive_pct": 100 * sum(1 for g in got if g["pct"] > 0) / len(got) if got else None,
            "drift_mean_pct_same_symbol_mix": base,
            "excess_mean_pct": (_mean(g["pct"] for g in got) - base) if got and base is not None else None,
        }
    cuts12 = _terciles([r["runup"].get(12) for r in rows if 12 in r["runup"]])
    by_runup = defaultdict(list)
    for r in rows:
        by_runup[_bucket(r["runup"].get(12), cuts12)].append(r)
    return {
        "forward": out,
        "runup12_r_mean": _mean(r["runup"][12] for r in rows if 12 in r["runup"]),
        "runup24_r_mean": _mean(r["runup"][24] for r in rows if 24 in r["runup"]),
        "runup12_terciles_cuts_r": cuts12,
        "by_runup12_tercile": {k: {"n": len(g), "expectancy_r": _mean(x["net_r"] for x in g),
                                   "win_rate_pct": 100 * sum(1 for x in g if x["net"] > 0) / len(g),
                                   "fwd24_mean_pct": _mean(x["fwd"][24]["pct"] for x in g if 24 in x["fwd"])}
                               for k, g in sorted(by_runup.items())},
    }


def loss_contexts(rows) -> dict[str, Any]:
    cuts_rv = _terciles([r["rvol"] for r in rows if r["rvol"] is not None])
    cuts_ru = _terciles([r["runup"].get(12) for r in rows if 12 in r["runup"]])
    enriched = []
    for r in rows:
        hb = "<4h" if r["hold_h"] < 4 else ("4-24h" if r["hold_h"] < 24 else ">=24h")
        enriched.append({**r, "mtf": str(r["mtf_aligned"]), "rvol_t": _bucket(r["rvol"], cuts_rv),
                         "runup_t": _bucket(r["runup"].get(12), cuts_ru), "hold_b": hb})
    return {
        "by_mtf_aligned": group_stats(enriched, "mtf"),
        "by_rvol_tercile": group_stats(enriched, "rvol_t"),
        "rvol_terciles_cuts": cuts_rv,
        "by_runup12_tercile": group_stats(enriched, "runup_t"),
        "by_hold_bucket": group_stats(enriched, "hold_b"),
    }


def portfolio_stats(res: RunResult, window: tuple[int, int]) -> dict[str, Any]:
    curve = [(t, eq) for t, eq, _ in res.equity if window[0] <= t < window[1]]
    expo = [(t, eq, g) for t, eq, g in res.equity if window[0] <= t < window[1]]
    eq0, eq1 = res.initial, curve[-1][1]
    n = len(curve)
    # simultaneous positions per bar, from trade intervals (+ positions still open at the end)
    events = []
    for tr in res.trades:
        events.append((tr.entry_time, 1))
        events.append((tr.exit_time, -1))
    for o in res.open_at_end:
        events.append((o["entry_time"], 1))
    events.sort()
    counts = []
    k, j = 0, 0
    for t, _ in curve:
        while j < len(events) and events[j][0] <= t:
            k += events[j][1]
            j += 1
        counts.append(k)
    unreal = sum(o["unrealized"] for o in res.open_at_end)
    return {
        "initial": eq0,
        "final_equity": eq1,
        "net_return_pct": 100 * (eq1 / eq0 - 1),
        "cagr_pct": 100 * ((eq1 / eq0) ** (N_YEAR_1H / n) - 1) if n else None,
        **max_drawdown(curve),
        "bars": n,
        "time_in_position_pct": 100 * sum(1 for _, _, g in expo if g > 0) / n,
        "exposure_mean_pct": 100 * _mean(g / eq for _, eq, g in expo),
        "exposure_max_pct": 100 * max(g / eq for _, eq, g in expo),
        "positions_mean": _mean(counts),
        "positions_max": max(counts) if counts else 0,
        "positions_hist": dict(sorted(Counter(counts).items())),
        "open_at_end": len(res.open_at_end),
        "unrealized_at_end": unreal,
        "cash_end": res.cash_end,
        "rejections": dict(res.rejections),
        "signals_seen": res.signals_seen,
        "daily_halt_days": res.halt_days,
        "ledger_ok": all(abs(float(v)) < 1e-6 for v in res.ledger_diff.values()),
    }


def fold_slices(res: RunResult) -> dict[str, Any]:
    """Continuous path cut by fold (NOT reset): equity at fold start/end and in-fold drawdown."""
    out = {}
    for name, s, e in fold_windows():
        pts = [(t, eq) for t, eq, _ in res.equity if s <= t < e]
        if not pts:
            continue
        start = pts[0][1]
        out[name] = {
            "equity_start": start,
            "equity_end": pts[-1][1],
            "return_pct": 100 * (pts[-1][1] / start - 1),
            "max_dd_pct": max_drawdown(pts)["max_dd_pct"],
        }
    return out


def filter_funnel(sigs: dict[str, list[BarSignal]], candles: dict[str, list[Candle]], window) -> dict[str, Any]:
    primary = Counter()
    long_rows = 0
    stage_fail = Counter()
    sole = Counter()
    regime_codes = Counter()
    buy_bars = 0
    total = 0
    for sym, ss in sigs.items():
        c = candles[sym]
        for i, s in enumerate(ss):
            if i < LIVE_WINDOW_BARS - 1 or not (window[0] <= c[i].time < window[1]):
                continue
            total += 1
            primary[s.primary] += 1
            if s.decision == "BUY":
                buy_bars += 1
            if s.direction.value != "LONG":
                continue
            long_rows += 1
            for st in s.failed:
                stage_fail[st] += 1
            if len(s.failed) == 1:
                sole[s.failed[0]] += 1
            for st, code in s.fail_codes:
                if st == "regime":
                    regime_codes[code] += 1
    return {
        "eligible_bars": total,
        "primary_share_pct": {k: 100 * v / total for k, v in primary.most_common()},
        "buy_bars": buy_bars,
        "long_bars": long_rows,
        "among_long_stage_fail_pct": {k: 100 * v / long_rows for k, v in stage_fail.most_common()},
        "among_long_sole_blocker_pct": {k: 100 * v / long_rows for k, v in sole.most_common()},
        "among_long_regime_codes_pct": {k: 100 * v / long_rows for k, v in regime_codes.most_common()},
        "note": "multi-label: stage_fail percentages overlap and must not be summed",
    }


def hold_benchmarks(candles: dict[str, list[Candle]], window, costs, initial: float) -> dict[str, Any]:
    """Context only (not a verdict): BTC buy & hold and an equal-weight basket of symbols eligible at start."""
    def path(syms):
        alloc = initial / len(syms)
        units = {}
        for s in syms:
            c = candles[s]
            i0 = next(i for i, x in enumerate(c) if x.time >= window[0])
            cm = costs[s]
            fill = c[i0].open * (1 + (cm.spread_bps + cm.slippage_bps) / 1e4)
            units[s] = alloc / (1 + cm.commission_bps / 1e4) / fill
        times = sorted({x.time for s in syms for x in candles[s] if window[0] <= x.time < window[1]})
        idx = {s: {x.time: x.close for x in candles[s]} for s in syms}
        last = {}
        curve = []
        for t in times:
            for s in syms:
                if t in idx[s]:
                    last[s] = idx[s][t]
            curve.append((t, sum(units[s] * last.get(s, 0.0) for s in syms)))
        return {"symbols": list(syms), "final_equity": curve[-1][1],
                "net_return_pct": 100 * (curve[-1][1] / initial - 1), **max_drawdown(curve)}

    eligible = [s for s, c in candles.items()
                if len(c) >= LIVE_WINDOW_BARS and c[LIVE_WINDOW_BARS - 1].time <= window[0]]
    return {"btc_hold": path(["BTCUSDT"]), "equal_weight_eligible_at_start": path(sorted(eligible))}
