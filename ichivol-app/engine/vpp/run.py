"""Run exactly the pre-registered VP-P runs (amendement VP0-2026-09-27b §P.2) and write the artifacts.

    python -m vpp download      # Vision zips (verified) -> vpp/data/raw
    python -m vpp build         # frozen series + sha256 manifest
    python -m vpp run           # signals, R1, R1-s, R2, R3, R4, C1, Ctx -> docs/vpp-artifacts/
"""

from __future__ import annotations

import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from research_lab.sim import BASE_COST, simulate

from vpp import FOLDS, INITIAL_CAPITAL, PROTOCOL_ID, PROTOCOL_VERSION, SEED, U3, U20
from vpp import diagnose as dg
from vpp.data import data_root, load_candles, load_manifest, series_rel
from vpp.paper import adverse_costs, paper_costs, paper_rules
from vpp.signals import build_feed, compute_all, concordance, concordance_sample

ART = Path(__file__).resolve().parents[3] / "docs" / "vpp-artifacts"
ORDER_SEEDS = (0, 1, 2, 3, 4)


def _ts(iso: str) -> int:
    return int(datetime.fromisoformat(iso).replace(tzinfo=timezone.utc).timestamp())


CONTINUOUS = (_ts(FOLDS[0][1]), _ts(FOLDS[-1][2]) + 86400)


def _git_head() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        return "unknown"


def _full_report(res, window, series, sigmap) -> dict[str, Any]:
    rows = dg.trade_rows(res.trades, series, sigmap)
    timing = dg.entry_timing(rows, series, window)  # also attaches each row's symbol drift
    return {
        "portfolio": dg.portfolio_stats(res, window),
        "trades": dg.trade_stats(rows),
        "ci_95_month_bootstrap": dg.expectancy_ci(rows),
        "by_symbol": dg.group_stats(rows, "symbol"),
        "by_fold": dg.group_stats(rows, "fold"),
        "by_year": dg.group_stats(rows, "year"),
        "by_exit_reason": dg.group_stats(rows, "exit_reason"),
        "continuous_path_by_fold": dg.fold_slices(res),
        "flags": dg.flag_stats(rows),
        "exit_quality": dg.exit_quality(rows),
        "entry_timing": timing,
        "loss_contexts": dg.loss_contexts(rows),
        "_rows": rows,
    }


def _short(res, window) -> dict[str, Any]:
    p = dg.portfolio_stats(res, window)
    return {k: p[k] for k in ("final_equity", "net_return_pct", "max_dd_pct", "time_in_position_pct",
                              "exposure_mean_pct", "daily_halt_days")} | {"n_trades": len(res.trades)}


def run_all(root: Path | None = None, workers: int = 4, c1_n: int = 300, v2: bool = False) -> dict[str, Any]:
    root = data_root(root)
    man = load_manifest(root)
    candles = {s: load_candles(s, "1h", root)[0] for s in U20}
    print("signals…", flush=True)
    sigs = compute_all(list(U20), root, workers)
    feeds = {s: build_feed(candles[s], sigs[s]) for s in U20}
    sigmap = {s: {x.time: x for x in sigs[s]} for s in U20}
    series = {s: dg.SeriesIndex(candles[s]) for s in U20}
    rules = paper_rules()
    cp, ca = paper_costs(U20), adverse_costs(U20)

    def sim(symbols, window, costs, seed=SEED):
        return simulate({s: feeds[s] for s in symbols}, rules, BASE_COST, window, initial=INITIAL_CAPITAL,
                        seed=seed, cost_by_symbol=costs)

    out: dict[str, Any] = {
        "protocol": PROTOCOL_ID,
        "protocol_version": PROTOCOL_VERSION,
        "git_head": _git_head(),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "seed": SEED,
        "initial_capital": INITIAL_CAPITAL,
        "continuous_window_utc": [dg._iso(CONTINUOUS[0]), dg._iso(CONTINUOUS[1] - 3600)],
        "rules": {k: v for k, v in rules.__dict__.items() if k != "decision_hook"},
        "costs_paper": {s: c.__dict__ for s, c in cp.items()},
        "costs_adverse": {s: c.__dict__ for s, c in ca.items()},
        "series_sha256": {f"{s}:{i}": man["files"][series_rel(s, i)]["sha256"] for s in U20 for i in ("1h", "4h")},
        "series_first_bar": {s: dg._iso(candles[s][0].time) for s in U20},
    }

    print("R1…", flush=True)
    r1 = sim(U20, CONTINUOUS, cp)
    out["R1"] = _full_report(r1, CONTINUOUS, series, sigmap)
    print("R1-s / R2 / R3 / R4…", flush=True)
    out["R1_s"] = {str(sd): _short(sim(U20, CONTINUOUS, cp, sd), CONTINUOUS) for sd in ORDER_SEEDS}
    r2 = sim(U20, CONTINUOUS, ca)
    out["R2"] = {k: v for k, v in _full_report(r2, CONTINUOUS, series, sigmap).items()
                 if k in ("portfolio", "trades", "by_exit_reason", "flags")}
    out["R3"] = {}
    for name, s, e in dg.fold_windows():
        r = sim(U20, (s, e), cp)
        rep = _full_report(r, (s, e), series, sigmap)
        out["R3"][name] = {"portfolio": rep["portfolio"], "trades": rep["trades"]}
    r4 = sim(U3, CONTINUOUS, cp)
    rep4 = _full_report(r4, CONTINUOUS, series, sigmap)
    out["R4"] = {k: v for k, v in rep4.items() if k != "_rows"}
    out["filters"] = dg.filter_funnel(sigs, candles, CONTINUOUS)
    out["context_hold"] = dg.hold_benchmarks(candles, CONTINUOUS, cp, INITIAL_CAPITAL)
    print("C1…", flush=True)
    sample = concordance_sample(candles, CONTINUOUS, n=c1_n)
    out["C1"] = concordance(sample, sigs, root, workers)

    ART.mkdir(parents=True, exist_ok=True)
    rows = out["R1"].pop("_rows")
    (ART / "vpp_results.json").write_text(json.dumps(out, indent=1, default=str), encoding="utf-8")
    (ART / "vpp_r1_trades.json").write_text(json.dumps(rows, default=str), encoding="utf-8")
    print("written", ART, flush=True)
    if not v2:
        return out

    # --- amendement VP0-2026-09-28 ---------------------------------------------------------------------------
    from vpp import event_study, fidelity, replay

    meta = {k: out[k] for k in ("protocol", "git_head", "generated_at", "seed")} | {
        "amendment": "VP0-2026-09-28"}
    print("C2…", flush=True)
    samples = fidelity.draw_samples(sigs, candles, CONTINUOUS)
    near, n_near_pool = fidelity.draw_near(samples.pop("_long_pool"), str(root), workers)
    samples["C2-SEUIL"] = near
    c2 = fidelity.compare(samples, root, workers, sigs=sigs)
    c2["_near_pool_size"] = n_near_pool
    (ART / "vpp_fidelity_c2.json").write_text(json.dumps(meta | c2, indent=1, default=str), encoding="utf-8")

    print("C3…", flush=True)
    wc = _window_most_full_hours(ART / "v1" / "vpp_r1_trades.json")
    windows = {"W-a": (_ts("2021-07-01"), _ts("2021-07-15")), "W-b": (_ts("2024-01-01"), _ts("2024-01-15")),
               "W-c": wc}
    c3 = {name: replay.compare_window(feeds, w) for name, w in windows.items()}
    (ART / "vpp_fidelity_c3.json").write_text(json.dumps(meta | c3, indent=1, default=str), encoding="utf-8")

    print("P3…", flush=True)
    p3 = event_study.run(sigs, candles, CONTINUOUS, cp, ca, r1.trades)
    (ART / "vpp_p3_event_study.json").write_text(json.dumps(meta | p3, indent=1, default=str), encoding="utf-8")
    print("written v2", flush=True)
    return out


def _window_most_full_hours(v1_trades_path: Path) -> tuple[int, int]:
    """W-c: the 14-day window (starting at UTC midnight) with the most hours at 10 open positions in R1 v1."""
    rows = json.loads(v1_trades_path.read_text(encoding="utf-8"))
    iv = [(_ts_hm(r["entry"]), _ts_hm(r["exit"])) for r in rows]
    counts: dict[int, int] = {}
    for a, b in iv:
        for t in range(a, b, 3600):
            counts[t] = counts.get(t, 0) + 1
    full = sorted(t for t, k in counts.items() if k >= 10)
    best, best_n = None, -1
    day0 = CONTINUOUS[0]
    for d in range(day0, CONTINUOUS[1] - 14 * 86400 + 1, 86400):
        n = sum(1 for t in full if d <= t < d + 14 * 86400)
        if n > best_n:
            best, best_n = d, n
    return best, best + 14 * 86400


def _ts_hm(s: str) -> int:
    return int(datetime.strptime(s, "%Y-%m-%d %H:%M").replace(tzinfo=timezone.utc).timestamp())
