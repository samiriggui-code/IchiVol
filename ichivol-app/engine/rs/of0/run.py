"""OF-0 — contrôles puis run unique (RS-07).

Usage (depuis ichivol-app/engine) :
    python -m rs.of0.run download --root <data>
    python -m rs.of0.run controls --root <data> --vp1 <BTCUSDT_spot_1h_*.json> --out <out>
    python -m rs.of0.run measure  --root <data> --out <out>

Choix d'implémentation (non couverts littéralement par RS-07, fixés avant le run) :
- les barres 1h incomplètes (< 3 400 s) restent dans les fenêtres ATR / RVOL
  (« barres disponibles », convention RS-03) mais ne sont ni mesurées ni cibles ;
- la cible exige que les barres t+1h et t+5h existent et soient valides ;
- l'IC bootstrap utilise les rangs de l'échantillon complet (voir stats.py).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from rs.of0 import (
    ALPHA,
    BOOT_N,
    C1_REL_TOL,
    C2_MAX_SHARE,
    DATA_END_EXCL_MS,
    FEATURES,
    HOUR_MS,
    HYPOTHESIS_ID,
    IC_MIN,
    MEASURE_START_MS,
    MIN_PERIODS_SAME_SIGN,
    MIN_SECONDS,
    PERIODS,
    PROTOCOL_VERSION,
    Q1_MIN_NEW,
    R2_NEW,
    R2_REDUNDANT,
    RVOL_WINDOW,
    SEED,
    TARGET_H,
)
from rs.of0.data import download_month, iter_hours, iter_seconds, load_vp1_1h, months, raw_dir, write_manifest, zip_name
from rs.of0.features import HourBar, aggregate, atr_series, baseline, bucket_width, design_row, of_features
from rs.of0.stats import day_block_bootstrap_ic, ols, ranks, spearman


# --- passe A : agrégation 1 s → 1h ----------------------------------------

def _aggregate_month(path: str) -> list[dict]:
    return [asdict(aggregate(t, secs)) for t, secs in iter_hours(iter_seconds(Path(path)))]


def _zip_paths(root: Path) -> list[str]:
    paths = [raw_dir(root) / zip_name(y, m) for y, m in months()]
    missing = [p.name for p in paths if not p.exists()]
    if missing:
        raise FileNotFoundError(f"zips manquants : {missing}")
    return [str(p) for p in paths]


def load_hours(out: Path) -> list[HourBar]:
    return [HourBar(**d) for d in json.loads((out / "hours_1h.json").read_text(encoding="utf-8"))]


def controls(root: Path, vp1: Path, out: Path) -> dict:
    with ProcessPoolExecutor() as ex:
        rows = [r for chunk in ex.map(_aggregate_month, _zip_paths(root)) for r in chunk]
    rows.sort(key=lambda r: r["t"])
    if any(r["t"] >= DATA_END_EXCL_MS for r in rows):
        raise AssertionError("barre >= 2025 agrégée")
    out.mkdir(parents=True, exist_ok=True)
    (out / "hours_1h.json").write_text(json.dumps(rows), encoding="utf-8")

    ref = load_vp1_1h(vp1)
    complete = [r for r in rows if r["n_seconds"] == 3600]
    worst_v = worst_tb = 0.0
    failures = []
    missing_ref = 0
    for r in complete:
        if r["t"] not in ref:
            missing_ref += 1
            continue
        v, tb = ref[r["t"]]
        ev = abs(r["volume"] - v) / max(abs(v), 1e-12)
        etb = abs(r["taker_buy"] - tb) / max(abs(tb), 1e-12)
        worst_v, worst_tb = max(worst_v, ev), max(worst_tb, etb)
        if ev > C1_REL_TOL or etb > C1_REL_TOL:
            failures.append({"t": r["t"], "agg": [r["volume"], r["taker_buy"]], "vp1": [v, tb]})
    c1 = {
        "n_hours": len(rows),
        "n_complete": len(complete),
        "n_lt_min_seconds": sum(1 for r in rows if r["n_seconds"] < MIN_SECONDS),
        "n_complete_missing_in_vp1": missing_ref,
        "worst_rel_err_volume": worst_v,
        "worst_rel_err_taker_buy": worst_tb,
        "n_failures": len(failures),
        "failures_sample": failures[:20],
        "pass": not failures,
    }
    (out / "c1.json").write_text(json.dumps(c1, indent=1), encoding="utf-8")
    return c1


# --- passe B : mesures F1–F5 ------------------------------------------------

def _features_month(args: tuple[str, dict[int, float]]) -> list[dict]:
    path, wmap = args
    res = []
    for t, secs in iter_hours(iter_seconds(Path(path))):
        w = wmap.get(t)
        if w is None or len(secs) < MIN_SECONDS or t < MEASURE_START_MS:
            continue
        f = of_features(secs, w)
        f["t"] = t
        res.append(f)
    return res


def measure(root: Path, out: Path) -> dict:
    c1 = json.loads((out / "c1.json").read_text(encoding="utf-8"))
    if not c1["pass"]:
        raise SystemExit("C1 en échec : arrêt (RS-07 §9)")
    hours = load_hours(out)
    atr = atr_series(hours)
    idx = {b.t: i for i, b in enumerate(hours)}
    wmap = {b.t: w for i, b in enumerate(hours) if i > 0 and (w := bucket_width(atr[i - 1])) is not None}

    with ProcessPoolExecutor() as ex:
        feats = [r for chunk in ex.map(_features_month, [(p, wmap) for p in _zip_paths(root)]) for r in chunk]
    feats.sort(key=lambda r: r["t"])

    # C2 — qualité de l'approximation.
    tot = sum(f["volume"] for f in feats)
    c2_share = sum(f["c2_multi_bucket_vol"] for f in feats) / tot if tot else None

    valid = {b.t for b in hours if b.n_seconds >= MIN_SECONDS}
    rows = []
    for f in feats:
        i = idx[f["t"]]
        bar = hours[i]
        base = baseline(bar, atr[i - 1], [b.volume for b in hours[max(0, i - RVOL_WINDOW) : i]])
        if base is None:
            continue
        t1, t5 = f["t"] + HOUR_MS, f["t"] + (TARGET_H + 1) * HOUR_MS
        y = None
        if t1 in valid and t5 in valid:
            y = math.log(hours[idx[t5]].open / hours[idx[t1]].open)
        rows.append({"t": f["t"], "x": design_row(base), "y": y, **{k: f[k] for k in FEATURES}})

    # Q1 — redondance.
    q1: dict[str, dict] = {}
    resid: dict[str, list[tuple[int, float, float | None]]] = {}
    for k in FEATURES:
        sub = [r for r in rows if r[k] is not None]
        beta, r2, e = ols([r["x"] for r in sub], [r[k] for r in sub])
        vals = sorted(r[k] for r in sub)
        q1[k] = {
            "n": len(sub),
            "r2": r2,
            "class": "redondante" if r2 >= R2_REDUNDANT else ("partielle" if r2 >= R2_NEW else "nouvelle"),
            "beta_std": beta,
            "quantiles": {p: vals[min(len(vals) - 1, int(p * len(vals)))] for p in (0.05, 0.25, 0.5, 0.75, 0.95)},
        }
        resid[k] = [(r["t"], ei, r["y"]) for r, ei in zip(sub, e)]
    q1_pass = sum(1 for k in FEATURES if q1[k]["r2"] < R2_NEW) >= Q1_MIN_NEW

    # Q2 — IC du résidu vs rendement 4h (mesures R² < 0,8 seulement).
    admitted = [k for k in FEATURES if q1[k]["r2"] < R2_REDUNDANT]
    alpha = ALPHA / len(admitted) if admitted else ALPHA
    q2: dict[str, dict] = {}
    for k in admitted:
        pts = [(t, e, y) for t, e, y in resid[k] if y is not None]
        es, ys = [p[1] for p in pts], [p[2] for p in pts]
        ic = spearman(es, ys)
        lo, hi = day_block_bootstrap_ic(
            ranks(es), ranks(ys), [p[0] // 86_400_000 for p in pts], n=BOOT_N, seed=SEED, alpha=alpha
        )
        per = {}
        for name, a, b in PERIODS:
            sel = [(e, y) for t, e, y in pts if a <= t < b]
            per[name] = spearman([s[0] for s in sel], [s[1] for s in sel]) if len(sel) > 2 else None
        same = sum(1 for v in per.values() if v is not None and ic is not None and v * ic > 0)
        ok = ic is not None and (lo > 0 or hi < 0) and abs(ic) >= IC_MIN and same >= MIN_PERIODS_SAME_SIGN
        q2[k] = {"n": len(pts), "ic": ic, "ci": [lo, hi], "ci_level": 1 - alpha, "by_period": per, "same_sign_periods": same, "pass": ok}
    q2_pass = any(v["pass"] for v in q2.values())

    fragile = c2_share is not None and c2_share > C2_MAX_SHARE
    if fragile:
        verdict = "APPROXIMATION FRAGILE (sans verdict, RS-07 §9 C2)"
    elif not q1_pass:
        verdict = "REDONDANT"
    elif not q2_pass:
        verdict = "NOUVEAU, NON PRÉDICTIF"
    else:
        verdict = "NOUVEAU ET PRÉDICTIF"

    manifest = root / "manifest.json"
    result = {
        "protocol": PROTOCOL_VERSION,
        "hypothesis": HYPOTHESIS_ID,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "manifest_sha256": hashlib.sha256(manifest.read_bytes()).hexdigest() if manifest.exists() else None,
        "data_label": "footprint approximé 1 s",
        "c1": {k: v for k, v in c1.items() if k != "failures_sample"},
        "c2_multi_bucket_volume_share": c2_share,
        "n_measured_hours": len(feats),
        "n_rows_with_baseline": len(rows),
        "n_rows_with_target": sum(1 for r in rows if r["y"] is not None),
        "q1": q1,
        "q1_pass": q1_pass,
        "q2_admitted": admitted,
        "q2": q2,
        "q2_pass": q2_pass,
        "verdict": verdict,
        "note_q2_residuals": "résidus Q2 = OLS ajustée sur tout l'échantillon (descriptif, point INFO revue #168)",
    }
    (out / "of0_result.json").write_text(json.dumps(result, indent=1, default=str), encoding="utf-8")
    return result


def main() -> None:
    p = argparse.ArgumentParser(prog="rs.of0.run")
    sub = p.add_subparsers(dest="cmd", required=True)
    d = sub.add_parser("download")
    d.add_argument("--root", type=Path, required=True)
    c = sub.add_parser("controls")
    c.add_argument("--root", type=Path, required=True)
    c.add_argument("--vp1", type=Path, required=True)
    c.add_argument("--out", type=Path, required=True)
    m = sub.add_parser("measure")
    m.add_argument("--root", type=Path, required=True)
    m.add_argument("--out", type=Path, required=True)
    a = p.parse_args()

    if a.cmd == "download":
        with ThreadPoolExecutor(4) as ex:
            entries = list(ex.map(lambda ym: download_month(a.root, *ym), months()))
        print("manifest sha256", write_manifest(a.root, entries))
    elif a.cmd == "controls":
        c1 = controls(a.root, a.vp1, a.out)
        print(json.dumps({k: v for k, v in c1.items() if k != "failures_sample"}, indent=1))
    else:
        r = measure(a.root, a.out)
        print("VERDICT", r["verdict"], "| C2", r["c2_multi_bucket_volume_share"])
        for k, v in r["q1"].items():
            print(k, "R2=%.3f" % v["r2"], v["class"], "n=%d" % v["n"])
        for k, v in r["q2"].items():
            print(k, "IC=%.4f" % v["ic"], "CI=[%.4f, %.4f]" % tuple(v["ci"]), "same=%d" % v["same_sign_periods"], "pass" if v["pass"] else "fail")


if __name__ == "__main__":
    main()
