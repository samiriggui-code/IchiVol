"""T-CYCLE Lab harness — synthetic truth + independent-target study (observe-only).

B3 — The previous walk-forward scored engine(T) against engine(T+h) on overlapping
windows (circular). This module splits validation:

(a) ``validate_cycle_synthetic`` — known sine / random-walk truth for period & phase.
(b) ``run_cycle_regime_study`` — product hypothesis « regime filter »:
    future efficiency-ratio (or |ret|/ATR) conditioned on regime at T, scored
    against surrogates (RW, AR(1), phase-randomized, shuffled returns).

``verdict.promote_to_decision`` is always false. Never touches decision/pipeline.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Sequence

from app.cycle.acf import estimate_acf
from app.cycle.consensus import median_period
from app.cycle.engine import CycleParams, compute_cycle_series, compute_cycle_state
from app.cycle.fft import estimate_fft
from app.cycle.hilbert import PHASE_GROUP_DELAY_BARS, estimate_hilbert
from app.cycle.preprocess import closes
from app.cycle.trend import efficiency_ratio
from app.cycle.types import CycleRegime, CycleState
from app.indicators.ichimoku import Candle


@dataclass(frozen=True)
class CycleStudyParams:
    window: int = 96
    min_period: float = 8.0
    max_period: float = 60.0
    horizon: int = 8
    seed: int = 7


def _circ_delta(a: float, b: float) -> float:
    d = abs(a - b) % 1.0
    return min(d, 1.0 - d)


def _mean_resultant_length(phases: list[float], truths: list[float]) -> float:
    """Circular correlation proxy: resultant length of unit vectors of phase error."""
    if not phases:
        return 0.0
    cx = sum(math.cos(2 * math.pi * (p - t)) for p, t in zip(phases, truths))
    sx = sum(math.sin(2 * math.pi * (p - t)) for p, t in zip(phases, truths))
    return math.hypot(cx, sx) / len(phases)


def make_sine_candles(
    n: int,
    period: float,
    *,
    amp: float = 0.02,
    base: float = 100.0,
    tf_sec: int = 3600,
    t0: int = 1_700_000_000,
) -> list[Candle]:
    out: list[Candle] = []
    for i in range(n):
        phase = 2.0 * math.pi * i / period
        price = base * math.exp(amp * math.sin(phase))
        t = t0 + i * tf_sec
        out.append(
            Candle(time=t, open=price, high=price * 1.001, low=price * 0.999, close=price, volume=1.0)
        )
    return out


def make_random_walk_candles(
    n: int,
    *,
    seed: int = 0,
    sigma: float = 0.01,
    base: float = 100.0,
    tf_sec: int = 3600,
    t0: int = 1_700_000_000,
) -> list[Candle]:
    rng = random.Random(seed)
    out: list[Candle] = []
    log_p = math.log(base)
    for i in range(n):
        log_p += rng.gauss(0.0, sigma)
        price = math.exp(log_p)
        t = t0 + i * tf_sec
        out.append(
            Candle(time=t, open=price, high=price * 1.001, low=price * 0.999, close=price, volume=1.0)
        )
    return out


def make_ar1_candles(
    n: int,
    *,
    phi: float = 0.9,
    seed: int = 0,
    sigma: float = 0.01,
    base: float = 100.0,
    tf_sec: int = 3600,
    t0: int = 1_700_000_000,
) -> list[Candle]:
    rng = random.Random(seed)
    out: list[Candle] = []
    log_p = math.log(base)
    eps = 0.0
    for i in range(n):
        eps = phi * eps + rng.gauss(0.0, sigma)
        log_p += eps
        price = math.exp(log_p)
        t = t0 + i * tf_sec
        out.append(
            Candle(time=t, open=price, high=price * 1.001, low=price * 0.999, close=price, volume=1.0)
        )
    return out


def phase_randomized_surrogate(candles: Sequence[Candle], *, seed: int) -> list[Candle]:
    """Keep amplitude spectrum of log-returns, randomize phases (stdlib DFT)."""
    import cmath

    rng = random.Random(seed)
    px = closes(candles)
    n = len(px)
    if n < 8:
        return list(candles)
    rets = [0.0]
    for i in range(1, n):
        if px[i - 1] > 0 and px[i] > 0:
            rets.append(math.log(px[i] / px[i - 1]))
        else:
            rets.append(0.0)
    # DFT
    spectrum: list[complex] = []
    for k in range(n):
        acc = 0j
        for t, x in enumerate(rets):
            acc += x * cmath.exp(-2j * math.pi * k * t / n)
        spectrum.append(acc)
    # Randomize phases for k=1..n-1 keeping conjugate symmetry
    new_spec = [spectrum[0]]
    for k in range(1, (n + 1) // 2):
        mag = abs(spectrum[k])
        ang = rng.random() * 2 * math.pi
        val = mag * cmath.exp(1j * ang)
        new_spec.append(val)
    if n % 2 == 0:
        new_spec.append(spectrum[n // 2])
    for k in range((n - 1) // 2, 0, -1):
        new_spec.append(new_spec[k].conjugate())
    # iDFT
    new_rets: list[float] = []
    for t in range(n):
        acc = 0j
        for k, ck in enumerate(new_spec):
            acc += ck * cmath.exp(2j * math.pi * k * t / n)
        new_rets.append(acc.real / n)
    log_p = math.log(px[0]) if px[0] > 0 else 0.0
    out: list[Candle] = []
    for i, c in enumerate(candles):
        if i > 0:
            log_p += new_rets[i]
        price = math.exp(log_p)
        out.append(
            Candle(
                time=c.time,
                open=price,
                high=price * 1.001,
                low=price * 0.999,
                close=price,
                volume=c.volume,
            )
        )
    return out


def shuffled_return_candles(candles: Sequence[Candle], *, seed: int) -> list[Candle]:
    rng = random.Random(seed)
    px = closes(candles)
    rets = []
    for i in range(1, len(px)):
        if px[i - 1] > 0 and px[i] > 0:
            rets.append(math.log(px[i] / px[i - 1]))
        else:
            rets.append(0.0)
    rng.shuffle(rets)
    log_p = math.log(px[0]) if px[0] > 0 else 0.0
    out: list[Candle] = [
        Candle(
            time=candles[0].time,
            open=px[0],
            high=px[0] * 1.001,
            low=px[0] * 0.999,
            close=px[0],
            volume=candles[0].volume,
        )
    ]
    for i, r in enumerate(rets):
        log_p += r
        price = math.exp(log_p)
        c = candles[i + 1]
        out.append(
            Candle(
                time=c.time,
                open=price,
                high=price * 1.001,
                low=price * 0.999,
                close=price,
                volume=c.volume,
            )
        )
    return out


def validate_cycle_synthetic(
    *,
    window: int = 128,
    periods: Sequence[float] = (12.0, 20.0, 40.0),
) -> dict:
    """(a) Estimation validation on known sines + RW false-positive rates."""
    params = CycleParams(window=window, min_period=8.0, max_period=min(80.0, window / 3.0))
    sine_rows: list[dict] = []
    for period in periods:
        n = max(window + 80, int(period * 12))
        candles = make_sine_candles(n, period)
        state = compute_cycle_state(candles, params)
        # Phase probe on last 40 bars after delay correction
        hilbert_phases: list[float] = []
        truths: list[float] = []
        circ_errs: list[float] = []
        # Re-estimate on trailing windows for phase track
        for end in range(n - 40, n):
            w0 = max(0, end + 1 - window)
            w_closes = [c.close for c in candles[w0 : end + 1]]
            fft = estimate_fft(
                w_closes, min_period=params.min_period, max_period=params.max_period
            )
            acf = estimate_acf(
                w_closes,
                min_period=int(params.min_period),
                max_period=int(min(params.max_period, window / 3.0)),
            )
            hint = median_period([fft.dominant_period, acf.dominant_period])
            h = estimate_hilbert(
                w_closes,
                min_period=params.min_period,
                max_period=params.max_period,
                period_hint=hint,
            )
            if h.phase is None or hint is None:
                continue
            # True phase of sine at bar `end`, compensated by known group delay
            i_eff = end - PHASE_GROUP_DELAY_BARS
            true_ph = (i_eff / period) % 1.0
            hilbert_phases.append(h.phase)
            truths.append(true_ph)
            circ_errs.append(_circ_delta(h.phase, true_ph))
        r = _mean_resultant_length(hilbert_phases, truths)
        mean_err = sum(circ_errs) / len(circ_errs) if circ_errs else 1.0
        sine_rows.append(
            {
                "true_period": period,
                "est_period": state.dominant_period_candles,
                "regime": state.regime.value,
                "phase_R": r,
                "phase_circ_err": mean_err,
                "n_phase": len(circ_errs),
                "methods": {
                    "fft": state.methods.get("fft", {}).get("dominant_period"),
                    "hilbert": state.methods.get("hilbert", {}).get("dominant_period"),
                    "acf": state.methods.get("acf", {}).get("dominant_period"),
                },
            }
        )

    # Regime rates on sine grid
    sine_regimes = {p: [] for p in (12.0, 20.0, 32.0, 48.0)}
    for period in sine_regimes:
        candles = make_sine_candles(max(window + 100, int(period * 14)), period)
        states = compute_cycle_series(candles, params)
        usable = states[window:]
        for st in usable:
            sine_regimes[period].append(st.regime.value)
    sine_regime_summary = {}
    for period, regs in sine_regimes.items():
        if not regs:
            continue
        n = len(regs)
        sine_regime_summary[str(period)] = {
            "CYCLE": regs.count("CYCLE") / n,
            "TREND": regs.count("TREND") / n,
            "TRANSITION": regs.count("TRANSITION") / n,
            "NOISE": regs.count("NOISE") / n,
            "n": n,
        }

    # RW false CYCLE rate (5 seeds)
    rw_cycle_rates: list[float] = []
    rw_trend_rates: list[float] = []
    for seed in range(5):
        candles = make_random_walk_candles(window + 400, seed=seed)
        states = compute_cycle_series(candles, params)
        usable = states[window:]
        n = len(usable) or 1
        rw_cycle_rates.append(sum(1 for s in usable if s.regime == CycleRegime.CYCLE) / n)
        rw_trend_rates.append(sum(1 for s in usable if s.regime == CycleRegime.TREND) / n)

    return {
        "ok": True,
        "kind": "synthetic_truth",
        "phase_period_rows": sine_rows,
        "sine_regime_fractions": sine_regime_summary,
        "random_walk": {
            "cycle_rate_mean": sum(rw_cycle_rates) / len(rw_cycle_rates),
            "cycle_rates": rw_cycle_rates,
            "trend_rate_mean": sum(rw_trend_rates) / len(rw_trend_rates),
            "trend_rates": rw_trend_rates,
        },
        "gates": {
            "phase_R_min": 0.9,
            "phase_err_max": 0.05,
            "sine_cycle_min": 0.80,
            "sine_trend_max": 0.10,
            "rw_cycle_max": 0.05,
        },
    }


def _future_efficiency(closes_px: Sequence[float], i: int, horizon: int) -> float | None:
    """Independent target: Kaufman ER on the *future* h bars after i (not in window end)."""
    j0 = i + 1
    j1 = i + 1 + horizon
    if j1 > len(closes_px):
        return None
    return efficiency_ratio(closes_px[j0:j1])


def _future_abs_ret_atr(candles: Sequence[Candle], i: int, horizon: int) -> float | None:
    """|close[i+h]/close[i]| / mean TR over same future window."""
    j1 = i + horizon
    if j1 >= len(candles) or i < 0:
        return None
    c0 = candles[i].close
    c1 = candles[j1].close
    if c0 <= 0:
        return None
    trs: list[float] = []
    for j in range(i + 1, j1 + 1):
        hi, lo, prev = candles[j].high, candles[j].low, candles[j - 1].close
        trs.append(max(hi - lo, abs(hi - prev), abs(lo - prev)))
    atr = sum(trs) / len(trs) if trs else 0.0
    if atr <= 1e-12:
        return None
    return abs(c1 - c0) / atr


def _regime_cycle_rate(candles: Sequence[Candle], params: CycleParams) -> float:
    states = compute_cycle_series(candles, params)
    usable = states[params.window :]
    if not usable:
        return 0.0
    return sum(1 for s in usable if s.regime == CycleRegime.CYCLE) / len(usable)


def run_cycle_regime_study(
    candles: Sequence[Candle],
    params: CycleStudyParams | None = None,
) -> dict:
    """(b) Product study: future ER conditioned on regime; surrogate CYCLE rates."""
    p = params or CycleStudyParams()
    cycle_params = CycleParams(
        window=p.window,
        min_period=p.min_period,
        max_period=min(p.max_period, p.window / 3.0),
    )
    states = compute_cycle_series(candles, cycle_params)
    px = closes(candles)
    n = len(states)
    min_i = max(p.window, 40)
    max_i = n - p.horizon - 1
    if max_i <= min_i:
        return {
            "ok": False,
            "error": "insufficient_bars",
            "n_bars": n,
            "need": min_i + p.horizon + 1,
        }

    # Collect future ER by regime
    by_regime: dict[str, list[float]] = {r.value: [] for r in CycleRegime}
    n_scored = 0
    for i in range(min_i, max_i + 1):
        st: CycleState = states[i]
        fut = _future_efficiency(px, i, p.horizon)
        if fut is None:
            continue
        by_regime[st.regime.value].append(fut)
        n_scored += 1

    def _mean(xs: list[float]) -> float | None:
        return sum(xs) / len(xs) if xs else None

    regime_future_er = {
        k: {"n": len(v), "mean_future_er": _mean(v)} for k, v in by_regime.items()
    }

    # Surrogate CYCLE rates (B3 nulls)
    rng_seed = p.seed
    surrogates = {
        "random_walk": _regime_cycle_rate(
            make_random_walk_candles(n, seed=rng_seed), cycle_params
        ),
        "ar1": _regime_cycle_rate(make_ar1_candles(n, seed=rng_seed + 1), cycle_params),
        "phase_randomized": _regime_cycle_rate(
            phase_randomized_surrogate(candles, seed=rng_seed + 2), cycle_params
        ),
        "shuffled_returns": _regime_cycle_rate(
            shuffled_return_candles(candles, seed=rng_seed + 3), cycle_params
        ),
    }
    series_cycle_rate = _regime_cycle_rate(candles, cycle_params)

    return {
        "ok": True,
        "kind": "regime_filter_study",
        "n_bars": n,
        "n_scored": n_scored,
        "horizon": p.horizon,
        "window": p.window,
        "series_cycle_rate": series_cycle_rate,
        "future_er_by_regime": regime_future_er,
        "surrogate_cycle_rates": surrogates,
        "verdict": {
            "promote_to_decision": False,
            "note": (
                "Independent future ER target (not engine self-prediction). "
                "Compare series_cycle_rate to surrogate_cycle_rates; "
                "promote_to_decision stays false until OOS multi-symbol + ablation."
            ),
        },
    }


def run_cycle_walk_forward(
    candles: Sequence[Candle],
    params: CycleStudyParams | None = None,
) -> dict:
    """Backward-compatible entry: runs (b) regime study (non-circular).

    For synthetic truth probes use ``validate_cycle_synthetic`` instead.
    """
    return run_cycle_regime_study(candles, params)
