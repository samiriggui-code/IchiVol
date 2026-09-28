"""Métriques et critères D1–D7 (RS-03 §8–§9). Bootstrap par mois calendaire, seed 7."""

from __future__ import annotations

import random
import statistics
from datetime import datetime, timezone
from typing import Any, Sequence

from rs import BOOT_N, FOLDS, SEED

Equity = Sequence[tuple[int, float, float]]


def _dt(t: int) -> datetime:
    return datetime.fromtimestamp(t, tz=timezone.utc)


def monthly_returns(eq: Equity, initial: float) -> dict[str, float]:
    """Rendement de chaque mois calendaire : equity au dernier close du mois / equity de fin du mois précédent."""
    ends: dict[str, float] = {}
    for t, e, _ in eq:
        ends[_dt(t).strftime("%Y-%m")] = e
    out: dict[str, float] = {}
    prev = initial
    for k in sorted(ends):
        out[k] = ends[k] / prev - 1.0
        prev = ends[k]
    return out


def boot_mean_ci(values: Sequence[float], *, n: int = BOOT_N, seed: int = SEED, alpha: float = 0.05) -> dict[str, float]:
    """Bootstrap i.i.d. sur les mois (chaque tirage reprend des mois entiers, tous actifs confondus)."""
    rng = random.Random(seed)
    vals = list(values)
    k = len(vals)
    if k == 0:
        return {"mean": float("nan"), "lo": float("nan"), "hi": float("nan"), "n_months": 0}
    means = sorted(sum(vals[rng.randrange(k)] for _ in range(k)) / k for _ in range(n))
    lo = means[int((alpha / 2) * (n - 1))]
    hi = means[int((1 - alpha / 2) * (n - 1))]
    return {"mean": sum(vals) / k, "lo": lo, "hi": hi, "n_months": k}


def max_drawdown(eq: Equity) -> dict[str, Any]:
    peak_v, peak_t = None, None
    mdd, trough_t, mdd_peak_t = 0.0, None, None
    for t, e, _ in eq:
        if peak_v is None or e > peak_v:
            peak_v, peak_t = e, t
        dd = e / peak_v - 1.0
        if dd < mdd:
            mdd, trough_t, mdd_peak_t = dd, t, peak_t
    recovery_days = None
    if trough_t is not None:
        peak_level = next(e for t, e, _ in eq if t == mdd_peak_t)
        for t, e, _ in eq:
            if t > trough_t and e >= peak_level:
                recovery_days = (t - trough_t) / 86400.0
                break
    return {
        "max_dd": mdd,
        "peak": _dt(mdd_peak_t).isoformat() if mdd_peak_t else None,
        "trough": _dt(trough_t).isoformat() if trough_t else None,
        "recovery_days": recovery_days,  # None = pas récupéré avant la fin de fenêtre
    }


def cagr(eq: Equity, initial: float) -> float | None:
    if not eq:
        return None
    days = (eq[-1][0] - eq[0][0]) / 86400.0 + 4 / 24
    return (eq[-1][1] / initial) ** (365.25 / days) - 1.0 if days > 0 and eq[-1][1] > 0 else None


def fold_returns(eq: Equity, initial: float) -> dict[str, float | None]:
    out: dict[str, float | None] = {}
    prev_end = initial
    for fid, a, b in FOLDS:
        lo = datetime.fromisoformat(a).replace(tzinfo=timezone.utc).timestamp()
        hi = datetime.fromisoformat(b).replace(tzinfo=timezone.utc).timestamp() + 86400
        inside = [e for t, e, _ in eq if lo <= t < hi]
        if not inside:
            out[fid] = None
            continue
        out[fid] = inside[-1] / prev_end - 1.0
        prev_end = inside[-1]
    return out


def summary(eq: Equity, initial: float) -> dict[str, Any]:
    exp = [g / e for _, e, g in eq if e > 0]
    dd = max_drawdown(eq)
    c = cagr(eq, initial)
    return {
        "capital_final": eq[-1][1] if eq else initial,
        "net_return": (eq[-1][1] / initial - 1.0) if eq else 0.0,
        "cagr": c,
        **dd,
        "calmar": (c / abs(dd["max_dd"])) if (c is not None and dd["max_dd"] < 0) else None,
        "exposure_mean": statistics.fmean(exp) if exp else 0.0,
        "exposure_max": max(exp) if exp else 0.0,
        "time_in_market": (sum(1 for x in exp if x > 0) / len(exp)) if exp else 0.0,
        "folds": fold_returns(eq, initial),
    }


def trade_stats(trades: Sequence[Any]) -> dict[str, Any]:
    closed = [t for t in trades if t.exit_reason != "open_at_end"]
    allt = list(trades)
    nets = [t.net for t in allt]
    wins = [t.net for t in closed if t.net > 0]
    losses = [t.net for t in closed if t.net <= 0]
    gross_total = sum(t.gross for t in allt)
    fees_total = sum(t.fees + t.friction for t in allt)
    ranked = sorted(nets, reverse=True)
    total = sum(nets)
    by_reason: dict[str, dict[str, float]] = {}
    for t in allt:
        r = by_reason.setdefault(t.exit_reason, {"n": 0, "net": 0.0})
        r["n"] += 1
        r["net"] += t.net
    by_sym: dict[str, float] = {}
    for t in allt:
        by_sym[t.symbol] = by_sym.get(t.symbol, 0.0) + t.net
    held_h = sorted(t.bars_held * 4 for t in closed)
    return {
        "n_closed": len(closed),
        "n_open_at_end": len(allt) - len(closed),
        "win_rate": len(wins) / len(closed) if closed else None,
        "avg_win": statistics.fmean(wins) if wins else None,
        "avg_loss": statistics.fmean(losses) if losses else None,
        "expectancy_eur": statistics.fmean([t.net for t in closed]) if closed else None,
        "expectancy_r": statistics.fmean([t.net / t.risk_amount for t in closed if t.risk_amount > 0]) if closed else None,
        "expectancy_pct_notional": statistics.fmean([t.net / t.notional for t in closed]) if closed else None,
        "profit_factor": (sum(wins) / abs(sum(losses))) if losses and sum(losses) != 0 else None,
        "duration_h_median": held_h[len(held_h) // 2] if held_h else None,
        "duration_h_mean": statistics.fmean(held_h) if held_h else None,
        "gross_total": gross_total,
        "costs_total": fees_total,
        "costs_share_of_gross": (fees_total / gross_total) if gross_total > 0 else None,
        "net_total_trades": total,
        "top1_share": (ranked[0] / total) if ranked and total > 0 else None,
        "top3_share": (sum(ranked[:3]) / total) if ranked and total > 0 else None,
        "top5_share": (sum(ranked[:5]) / total) if ranked and total > 0 else None,
        "net_without_top3": total - sum(ranked[:3]),
        "by_exit_reason": by_reason,
        "net_by_symbol": by_sym,
    }


def verdict(
    *,
    base: dict[str, Any],
    adverse_net_return: float,
    monthly_ci: dict[str, float],
    delta_b7_ci: dict[str, float] | None,
    calmar_b0e: float | None,
    trades: dict[str, Any],
) -> dict[str, Any]:
    folds_pos = sum(1 for v in base["folds"].values() if v is not None and v > 0)
    syms_pos = sum(1 for v in trades["net_by_symbol"].values() if v > 0)
    d = {
        "D1": base["net_return"] > 0 and monthly_ci["lo"] > 0,
        "D2": base["max_dd"] >= -0.15,
        "D3": None if delta_b7_ci is None else delta_b7_ci["lo"] > 0,
        "D4": base["calmar"] is not None and calmar_b0e is not None and base["calmar"] > calmar_b0e,
        "D5": syms_pos >= 2 and folds_pos >= 4,
        "D6": adverse_net_return > 0,
        "D7": trades["n_closed"] >= 30,
    }
    if base["net_return"] <= 0 or base["max_dd"] < -0.15:
        v = "REJETÉ"
    elif all(x is True for x in d.values()):
        v = "CANDIDAT À VALIDATION SUPPLÉMENTAIRE"
    elif d["D3"] is None and all(x is True for k, x in d.items() if k != "D3"):
        v = "EN ATTENTE DE B7-P (D3)"
    else:
        v = "NON CONCLUANT"
    return {"criteria": d, "folds_positive": folds_pos, "symbols_positive": syms_pos, "verdict": v}
