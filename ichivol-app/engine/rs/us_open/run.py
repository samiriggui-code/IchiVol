"""RS-U0 — calcul de la porte (RS-05 §4–§6).

Usage (depuis ichivol-app/engine) :
    python -m rs.us_open.run download --root <dir>
    python -m rs.us_open.run measure --root <dir> --out <dir>
"""

from __future__ import annotations

import argparse
import json
import random
import statistics
from datetime import date, datetime, timezone
from pathlib import Path

from rs.us_open import (
    ANCHOR_MINUTES,
    BOOT_N,
    DAY_END,
    DAY_START,
    G1_TOP,
    G3_MAX_RANK,
    G4_MIN_EVENTS,
    HYPOTHESIS_ID,
    MIN_ASSETS,
    PROTOCOL_VERSION,
    SEED,
    SYMBOLS,
    TARGET_MINUTE,
    round_trip_cost_bps,
)
from rs.us_open.data import Bars, download, load, write_manifest
from rs.us_open.measure import Anchor, measure
from rs.us_open.nyse import PARIS, anchor_ms, nyse_days, us_dst


def _median(xs: list[float]) -> float | None:
    return statistics.median(xs) if xs else None


def _mean(xs: list[float]) -> float | None:
    return sum(xs) / len(xs) if xs else None


def bootstrap_mean_ci(per_day: list[float | None], n: int = BOOT_N, seed: int = SEED) -> tuple[float, float] | None:
    """IC95 percentile de la moyenne des événements, tirage de jours entiers (RS-05 §4)."""
    if not any(v is not None for v in per_day):
        return None
    rng = random.Random(seed)
    k = len(per_day)
    means: list[float] = []
    for _ in range(n):
        s = 0.0
        c = 0
        for _j in range(k):
            v = per_day[rng.randrange(k)]
            if v is not None:
                s += v
                c += 1
        if c:
            means.append(s / c)
    means.sort()
    return means[int(0.025 * len(means))], means[min(len(means) - 1, int(0.975 * len(means)))]


def anchor_stats(results: list[Anchor], cost: float) -> dict:
    counts: dict[str, int] = {}
    for a in results:
        counts[a.status] = counts.get(a.status, 0) + 1
    evts = [a for a in results if a.status == "event"]
    r = [a.r_bps for a in evts if a.r_bps is not None]
    valid = [a for a in results if a.status != "excluded"]
    return {
        "n_days": len(results),
        "n_valid": len(valid),
        "status": counts,
        "vol15": _median([a.vol15 for a in valid if a.vol15 is not None]),
        "volshare15": _median([a.volshare15 for a in valid if a.volshare15 is not None]),
        "n_evt": len(evts),
        "p_evt": len(evts) / len(valid) if valid else None,
        "mean_gross": _mean(r),
        "mean_net": (m - cost) if (m := _mean(r)) is not None else None,
        "hit": sum(1 for x in r if x > 0) / len(r) if r else None,
    }


def _subset(results: list[Anchor], days: list[date], pred) -> list[Anchor]:
    return [a for a, d in zip(results, days) if pred(a, d)]


def measure_symbol(symbol: str, bars: Bars, days: list[date]) -> dict:
    cost = round_trip_cost_bps(symbol)
    per_anchor: dict[int, list[Anchor]] = {m: [measure(bars, anchor_ms(d, m)) for d in days] for m in ANCHOR_MINUTES}
    table = {m: anchor_stats(res, cost) for m, res in per_anchor.items()}

    def rank(key: str, m: int) -> int:
        vals = sorted(
            ((table[x][key] if table[x][key] is not None else float("-inf")), x) for x in ANCHOR_MINUTES
        )
        vals.reverse()
        return 1 + [x for _v, x in vals].index(m)

    tgt = per_anchor[TARGET_MINUTE]
    t = table[TARGET_MINUTE]
    per_day = [a.r_bps if a.status == "event" else None for a in tgt]
    ci = bootstrap_mean_ci(per_day)

    g1 = rank("vol15", TARGET_MINUTE) <= G1_TOP
    g2 = t["mean_net"] is not None and t["mean_net"] > 0 and ci is not None and ci[0] > 0
    g3 = rank("mean_net", TARGET_MINUTE) <= G3_MAX_RANK
    g4 = t["n_evt"] >= G4_MIN_EVENTS

    # Descriptifs 09:30 (RS-05 §6).
    evts = [a for a in tgt if a.status == "event"]
    breakdown = {
        "long": anchor_stats([a for a in tgt if a.status == "event" and a.side == 1], cost),
        "short": anchor_stats([a for a in tgt if a.status == "event" and a.side == -1], cost),
        "by_year": {
            str(y): anchor_stats(_subset(tgt, days, lambda a, d, y=y: d.year == y), cost)
            for y in sorted({d.year for d in days})
        },
        "us_dst": anchor_stats(_subset(tgt, days, lambda a, d: us_dst(d)), cost),
        "us_std": anchor_stats(_subset(tgt, days, lambda a, d: not us_dst(d)), cost),
    }
    vols = sorted(a.vol15 for a in tgt if a.vol15 is not None)
    if vols:
        q1, q2 = vols[len(vols) // 3], vols[2 * len(vols) // 3]
        breakdown["vol15_tercile"] = {
            "low": anchor_stats([a for a in tgt if a.vol15 is not None and a.vol15 < q1], cost),
            "mid": anchor_stats([a for a in tgt if a.vol15 is not None and q1 <= a.vol15 < q2], cost),
            "high": anchor_stats([a for a in tgt if a.vol15 is not None and a.vol15 >= q2], cost),
        }
    mae = sorted(a.mae_r for a in evts if a.mae_r is not None)
    mfe = sorted(a.mfe_r for a in evts if a.mfe_r is not None)

    def q(xs: list[float], p: float) -> float | None:
        return xs[min(len(xs) - 1, int(p * len(xs)))] if xs else None

    breakdown["mae_r"] = {p: q(mae, p) for p in (0.25, 0.5, 0.75, 0.9)}
    breakdown["mfe_r"] = {p: q(mfe, p) for p in (0.25, 0.5, 0.75, 0.9)}

    # 15h30 Paris fixe vs 09:30 NY, jours où les deux diffèrent (descriptif).
    diff_days = [d for d in days if anchor_ms(d, 15 * 60 + 30, PARIS) != anchor_ms(d, TARGET_MINUTE)]
    breakdown["paris_1530_mismatch_days"] = {
        "n_days": len(diff_days),
        "ny_0930": anchor_stats([measure(bars, anchor_ms(d, TARGET_MINUTE)) for d in diff_days], cost),
        "paris_1530": anchor_stats([measure(bars, anchor_ms(d, 15 * 60 + 30, PARIS)) for d in diff_days], cost),
    }

    return {
        "symbol": symbol,
        "cost_rt_bps": cost,
        "table": {f"{m // 60:02d}:{m % 60:02d}": table[m] for m in ANCHOR_MINUTES},
        "target": {
            **t,
            "ci95_mean_gross": ci,
            "rank_vol15": rank("vol15", TARGET_MINUTE),
            "rank_net": rank("mean_net", TARGET_MINUTE),
        },
        "gates": {"G1": g1, "G2": g2, "G3": g3, "G4": g4},
        "breakdown": breakdown,
    }


def verdict(per_symbol: list[dict]) -> str:
    g4 = sum(1 for s in per_symbol if s["gates"]["G4"])
    ok = sum(1 for s in per_symbol if s["gates"]["G2"] and s["gates"]["G3"] and s["gates"]["G4"])
    fail = sum(1 for s in per_symbol if s["gates"]["G4"] and not (s["gates"]["G2"] and s["gates"]["G3"]))
    if ok >= MIN_ASSETS:
        return "PASSE"
    if g4 >= MIN_ASSETS and fail >= MIN_ASSETS:
        return "ÉCHEC"
    return "NON CONCLUANT"


def main() -> None:
    p = argparse.ArgumentParser(prog="rs.us_open.run")
    sub = p.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("download")
    d.add_argument("--root", type=Path, required=True)
    m = sub.add_parser("measure")
    m.add_argument("--root", type=Path, required=True)
    m.add_argument("--out", type=Path, required=True)
    args = p.parse_args()

    if args.cmd == "download":
        manifest = {s: download(s, args.root) for s in SYMBOLS}
        print("manifest sha256", write_manifest(args.root, manifest))
        return

    days = nyse_days(DAY_START, DAY_END)
    per_symbol = []
    for s in SYMBOLS:
        bars = load(s, args.root)
        print(f"{s}: {len(bars)} barres 5m, {len(days)} jours NYSE", flush=True)
        per_symbol.append(measure_symbol(s, bars, days))
    manifest_path = args.root / "manifest.json"
    out = {
        "protocol": PROTOCOL_VERSION,
        "hypothesis": HYPOTHESIS_ID,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "window": [DAY_START.isoformat(), DAY_END.isoformat()],
        "manifest_sha256": __import__("hashlib").sha256(manifest_path.read_bytes()).hexdigest()
        if manifest_path.exists()
        else None,
        "verdict": verdict(per_symbol),
        "symbols": per_symbol,
    }
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "rs_u0_result.json").write_text(json.dumps(out, indent=1, default=str), encoding="utf-8")
    print("VERDICT", out["verdict"])
    for s in per_symbol:
        t = s["target"]
        print(
            s["symbol"], s["gates"], "n_evt", t["n_evt"], "mean_net", t["mean_net"],
            "ci", t["ci95_mean_gross"], "rank_net", t["rank_net"], "rank_vol15", t["rank_vol15"],
        )


if __name__ == "__main__":
    main()
