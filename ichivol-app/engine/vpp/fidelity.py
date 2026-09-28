"""VP-P fidelity controls (amendement VP0-2026-09-28 Q.2 / Q.3).

C2 — decision-determining VALUES, not only the BUY label: live window (299 closed 1h bars, 299 closed 4h bars at the
     decision instant) vs the full-history computation used by the simulator, on BUY / near-threshold / sole-blocker
     samples.
C3 — see vpp/replay.py (position life cycle + shared capital through the real paper engine).
"""

from __future__ import annotations

import random
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.agents import ichimoku_agent, rvol_agent
from app.agents.types import Direction
from app.backtest.experiments import _align_mtf_directions
from app.decision.pipeline import build_pipeline
from app.indicators.adx import compute_adx
from app.indicators.atr import compute_atr
from app.indicators.cvd import compute_cvd
from app.indicators.donchian import compute_donchian
from app.indicators.ichimoku import Candle
from app.indicators.location import compute_location
from app.indicators.structure import compute_structure

from vpp import LIVE_WINDOW_BARS, SEED
from vpp.data import load_candles

HTF_SECONDS = 14_400
LTF_SECONDS = 3_600
PER_SYMBOL_YEAR = 8
N_NEAR = 150
N_SOLE = 150


def _values(candles: list[Candle], htf: list[Candle], idxs: list[int], live_htf: bool) -> dict[int, dict[str, Any]]:
    """Every decision-determining value at bar indices ``idxs`` (same stack as research_lab.signals)."""
    ichi = ichimoku_agent.analyze(candles)
    rvol = rvol_agent.analyze(candles)
    struct = compute_structure(candles)
    atr = compute_atr(candles)
    loc = compute_location(candles, struct)
    cvd = compute_cvd(candles)
    adx = compute_adx(candles)
    don = compute_donchian(candles)
    htf_out = ichimoku_agent.analyze(htf) if len(htf) >= 2 else []
    if live_htf:
        # live: scan_symbol reads analyze(closed htf)[-1] at the decision instant
        mtf_last = htf_out[-1].direction if htf_out else None
    else:
        mtf = _align_mtf_directions(candles, htf, htf_out, HTF_SECONDS) if htf_out else [None] * len(candles)
    out = {}
    for i in idxs:
        io = ichi[i]
        m = mtf_last if live_htf else mtf[i]
        aligned = (m == io.direction) if m is not None and m != Direction.NEUTRAL and io.direction != Direction.NEUTRAL else None
        p = build_pipeline(io, rvol[i], struct[i], atr[i], aligned, loc[i], cvd[i], None, adx[i], don[i])
        prev_upper = don[i].upper
        out[i] = {
            "decision": p.decision,
            "direction": p.direction.value,
            "stages": {s.id.value: s.status.value for s in p.stages},
            "atr": atr[i].atr,
            "atr_percentile": atr[i].percentile,
            "atr_regime": atr[i].regime.value,
            "stop_distance": atr[i].suggested_stop_distance,
            "adx": adx[i].adx,
            "adx_strength": adx[i].strength.value,
            "donchian": don[i].breakout.value,
            "donchian_upper": prev_upper,
            "rvol": rvol[i].metadata.get("rvol"),
            "rvol_level": str(rvol[i].metadata.get("anomaly_level")),
            "close": candles[i].close,
            "mtf_aligned": aligned,
        }
    return out


@lru_cache(maxsize=4)
def _series(symbol: str, root: str | None) -> tuple[list[Candle], list[Candle]]:
    r = Path(root) if root else None
    return load_candles(symbol, "1h", r)[0], load_candles(symbol, "4h", r)[0]


def _live_one(args: tuple[str, int, str | None]) -> tuple[str, int, dict[str, Any]]:
    symbol, i, root = args
    c1, c4 = _series(symbol, root)
    decision_s = c1[i].time + LTF_SECONDS
    lo = max(0, i - (LIVE_WINDOW_BARS - 1))
    window = c1[lo: i + 1]
    htf = [h for h in c4 if h.time + HTF_SECONDS <= decision_s][-LIVE_WINDOW_BARS:]
    return symbol, i, _values(window, htf, [len(window) - 1], live_htf=True)[len(window) - 1]


def _full_one(args: tuple[str, list[int], str | None]) -> tuple[str, dict[int, dict[str, Any]]]:
    symbol, idxs, root = args
    c1, c4 = _series(symbol, root)
    return symbol, _values(c1, c4, idxs, live_htf=False)


def draw_samples(sigs: dict[str, list], candles: dict[str, list[Candle]], window: tuple[int, int]) -> dict[str, list]:
    """C2-BUY (stratified symbol × year), C2-SEUIL (near a threshold), C2-SEUL (regime sole blocker). Seed 7."""
    rng = random.Random(SEED)
    buys: dict[tuple[str, int], list[tuple[str, int]]] = defaultdict(list)
    sole: list[tuple[str, int]] = []
    long_idx: list[tuple[str, int]] = []
    for s in sorted(sigs):
        c = candles[s]
        for i, x in enumerate(sigs[s]):
            if i < LIVE_WINDOW_BARS - 1 or not (window[0] <= c[i].time < window[1]):
                continue
            if x.decision == "BUY":
                buys[(s, datetime.fromtimestamp(c[i].time, timezone.utc).year)].append((s, i))
            elif x.direction == Direction.LONG:
                long_idx.append((s, i))
                if x.failed == ("regime",):
                    sole.append((s, i))
    c2_buy = []
    for key in sorted(buys):
        pool = buys[key]
        c2_buy += rng.sample(pool, min(PER_SYMBOL_YEAR, len(pool)))
    c2_sole = rng.sample(sole, min(N_SOLE, len(sole)))
    return {"C2-BUY": sorted(c2_buy), "C2-SEUL": sorted(c2_sole), "_long_pool": long_idx}


def _is_near(v: dict[str, Any]) -> bool:
    p, adx, atr, up, rv = v["atr_percentile"], v["adx"], v["atr"], v["donchian_upper"], v["rvol"]
    return bool(
        (p is not None and (abs(p - 0.15) <= 0.02 or abs(p - 0.90) <= 0.02))
        or (adx is not None and abs(adx - 25.0) <= 1.0)
        or (atr and up is not None and abs(v["close"] - up) <= 0.1 * atr)
        or (rv is not None and abs(rv - 0.7) <= 0.05)
    )


def draw_near(long_pool: list[tuple[str, int]], root: str | None, workers: int) -> tuple[list[tuple[str, int]], int]:
    """C2-SEUIL: values are needed to know what is near a threshold -> scan the LONG non-BUY pool on full history."""
    by_sym: dict[str, list[int]] = defaultdict(list)
    for s, i in long_pool:
        by_sym[s].append(i)
    with ProcessPoolExecutor(max_workers=workers) as ex:
        full = dict(ex.map(_full_one, [(s, idx, root) for s, idx in sorted(by_sym.items())]))
    near = [(s, i) for s in sorted(full) for i in sorted(full[s]) if _is_near(full[s][i])]
    return sorted(random.Random(SEED).sample(near, min(N_NEAR, len(near)))), len(near)


def compare(
    samples: dict[str, list[tuple[str, int]]], root: Path | None, workers: int = 4, sigs: dict | None = None,
) -> dict[str, Any]:
    r = str(root) if root else None
    all_pts = sorted({p for k, v in samples.items() if not k.startswith("_") for p in v})
    by_sym: dict[str, list[int]] = defaultdict(list)
    for s, i in all_pts:
        by_sym[s].append(i)
    with ProcessPoolExecutor(max_workers=workers) as ex:
        full = dict(ex.map(_full_one, [(s, idx, r) for s, idx in sorted(by_sym.items())]))
        live = {(s, i): v for s, i, v in ex.map(_live_one, [(s, i, r) for s, i in all_pts], chunksize=10)}
    out: dict[str, Any] = {}
    if sigs is not None:
        # the full-history values recomputed here must reproduce the simulator's own decisions exactly
        out["_sim_decision_mismatches"] = sum(
            1 for s, i in all_pts if full[s][i]["decision"] != sigs[s][i].decision
        )
    for name, pts in samples.items():
        if name.startswith("_"):
            continue
        agree: Counter = Counter()
        rel_atr: list[float] = []
        dis: list[dict[str, Any]] = []
        for s, i in pts:
            f, lv = full[s][i], live[(s, i)]
            for k in ("decision", "direction", "atr_regime", "adx_strength", "donchian", "rvol_level"):
                agree[k] += f[k] == lv[k]
            for st, val in f["stages"].items():
                agree[f"stage:{st}"] += val == lv["stages"].get(st)
            if f["atr"] and lv["atr"]:
                rel_atr.append(abs(lv["atr"] / f["atr"] - 1))
            if f["decision"] != lv["decision"]:
                dis.append({
                    "symbol": s, "index": i,
                    "bar_utc": datetime.fromtimestamp(_series(s, r)[0][i].time, timezone.utc).isoformat(),
                    "full_history": f["decision"], "live_window": lv["decision"],
                    "direction": "BUY_sim_only" if f["decision"] == "BUY" else (
                        "BUY_live_only" if lv["decision"] == "BUY" else "other"),
                    "full": {k: f[k] for k in ("atr_percentile", "adx", "donchian", "rvol", "stages")},
                    "live": {k: lv[k] for k in ("atr_percentile", "adx", "donchian", "rvol", "stages")},
                })
        n = len(pts)
        rel_atr.sort()
        out[name] = {
            "n": n,
            "agree_pct": {k: 100 * v / n for k, v in sorted(agree.items())} if n else {},
            "atr_rel_diff_median": rel_atr[len(rel_atr) // 2] if rel_atr else None,
            "atr_rel_diff_max": rel_atr[-1] if rel_atr else None,
            "stop_distance_rel_diff_max": rel_atr[-1] if rel_atr else None,  # stop = 1.5 x ATR in both
            "disagreements": dis,
            "buy_sim_only": sum(1 for d in dis if d["direction"] == "BUY_sim_only"),
            "buy_live_only": sum(1 for d in dis if d["direction"] == "BUY_live_only"),
            "symbols": len({s for s, _ in pts}),
            "years": dict(Counter(datetime.fromtimestamp(_series(s, r)[0][i].time, timezone.utc).year
                                  for s, i in pts)),
        }
    return out
