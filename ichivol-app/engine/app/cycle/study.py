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
    # P1 — API/agent default 5 (was 20); clamp [1, 50] at run time.
    null_draws: int = 5
    # P1 — score one bar every ``stride`` in the future-ER loop (default = horizon).
    stride: int | None = None


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
    noise: float = 0.0,
    seed: int = 0,
    base: float = 100.0,
    tf_sec: int = 3600,
    t0: int = 1_700_000_000,
) -> list[Candle]:
    rng = random.Random(seed)
    out: list[Candle] = []
    for i in range(n):
        phase = 2.0 * math.pi * i / period
        signal = amp * math.sin(phase)
        if noise > 0:
            signal += rng.gauss(0.0, noise)
        price = base * math.exp(signal)
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
    drift: float = 0.0,
    base: float = 100.0,
    tf_sec: int = 3600,
    t0: int = 1_700_000_000,
) -> list[Candle]:
    rng = random.Random(seed)
    out: list[Candle] = []
    log_p = math.log(base)
    for i in range(n):
        log_p += drift + rng.gauss(0.0, sigma)
        price = math.exp(log_p)
        t = t0 + i * tf_sec
        out.append(
            Candle(time=t, open=price, high=price * 1.001, low=price * 0.999, close=price, volume=1.0)
        )
    return out


def make_garch_candles(
    n: int,
    *,
    seed: int = 0,
    omega: float = 1e-6,
    alpha: float = 0.08,
    beta: float = 0.90,
    base: float = 100.0,
    tf_sec: int = 3600,
    t0: int = 1_700_000_000,
) -> list[Candle]:
    """Simple GARCH(1,1) on log-returns (stdlib)."""
    rng = random.Random(seed)
    out: list[Candle] = []
    log_p = math.log(base)
    var = omega / max(1e-12, 1.0 - alpha - beta)
    eps = 0.0
    for i in range(n):
        var = omega + alpha * eps * eps + beta * var
        eps = math.sqrt(max(var, 1e-18)) * rng.gauss(0.0, 1.0)
        log_p += eps
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


def _future_er_gap_cycle_vs_global(
    candles: Sequence[Candle],
    params: CycleParams,
    *,
    horizon: int,
    stride: int = 1,
) -> tuple[float | None, float, dict[str, list[float]]]:
    """Mean future ER on CYCLE bars minus mean future ER on all scored bars.

    P1 — ``stride`` scores one bar every ``stride`` steps and passes the same
    stride into ``compute_cycle_series`` (fewer windows → /study under budget).
    """
    step = max(1, int(stride))
    states = compute_cycle_series(candles, params, stride=step)
    px = closes(candles)
    n = len(states)
    min_i = max(params.window, 40)
    max_i = n - horizon - 1
    by_regime: dict[str, list[float]] = {r.value: [] for r in CycleRegime}
    all_er: list[float] = []
    min_bars = max(32, int(params.min_period) * 3)
    scored_states = [states[i] for i in range(min_bars - 1, n, step)]
    cycle_rate = (
        sum(1 for s in scored_states if s.regime == CycleRegime.CYCLE) / len(scored_states)
        if scored_states
        else 0.0
    )
    for i in range(min_i, max_i + 1, step):
        fut = _future_efficiency(px, i, horizon)
        if fut is None:
            continue
        by_regime[states[i].regime.value].append(fut)
        all_er.append(fut)
    if not all_er:
        return None, cycle_rate, by_regime
    global_mean = sum(all_er) / len(all_er)
    cycle_ers = by_regime[CycleRegime.CYCLE.value]
    if not cycle_ers:
        return None, cycle_rate, by_regime
    cycle_mean = sum(cycle_ers) / len(cycle_ers)
    return cycle_mean - global_mean, cycle_rate, by_regime


def _percentile_of(value: float, sample: list[float]) -> float | None:
    """Empirical percentile of ``value`` in ``sample`` (fraction in [0, 1])."""
    if not sample:
        return None
    below = sum(1 for x in sample if x < value)
    equal = sum(1 for x in sample if x == value)
    return (below + 0.5 * equal) / len(sample)


def run_cycle_regime_study(
    candles: Sequence[Candle],
    params: CycleStudyParams | None = None,
) -> dict:
    """(b) Product study: future ER conditioned on regime; surrogate CYCLE rates.

    P1 — ``null_draws`` default 5 (clamped [1, 50]); ``stride`` defaults to
    ``horizon``. Publishes ``null_draws``, ``stride``, and percentile resolution
    ``1/(n_gaps+1)`` per null family.
    """
    p = params or CycleStudyParams()
    cycle_params = CycleParams(
        window=p.window,
        min_period=p.min_period,
        max_period=min(p.max_period, p.window / 3.0),
    )
    stride = int(p.stride) if p.stride is not None else int(p.horizon)
    stride = max(1, stride)
    n_draws = max(1, min(50, int(p.null_draws)))

    observed_gap, series_cycle_rate, by_regime = _future_er_gap_cycle_vs_global(
        candles, cycle_params, horizon=p.horizon, stride=stride
    )
    n = len(candles)
    n_scored = sum(len(v) for v in by_regime.values())
    if n_scored == 0:
        return {
            "ok": False,
            "error": "insufficient_bars",
            "n_bars": n,
            "need": max(p.window, 40) + p.horizon + 1,
            "null_draws": n_draws,
            "stride": stride,
        }

    def _mean(xs: list[float]) -> float | None:
        return sum(xs) / len(xs) if xs else None

    regime_future_er = {
        k: {"n": len(v), "mean_future_er": _mean(v)} for k, v in by_regime.items()
    }

    null_seed_base = {
        "random_walk": 1000,
        "ar1": 2000,
        "phase_randomized": 3000,
        "shuffled_returns": 4000,
        "garch": 5000,
    }
    # P4 — wire make_garch_candles into nulls (was dead code).
    null_specs = (
        ("random_walk", lambda s: make_random_walk_candles(n, seed=s)),
        ("ar1", lambda s: make_ar1_candles(n, seed=s)),
        (
            "phase_randomized",
            lambda s: phase_randomized_surrogate(candles, seed=s),
        ),
        ("shuffled_returns", lambda s: shuffled_return_candles(candles, seed=s)),
        ("garch", lambda s: make_garch_candles(n, seed=s)),
    )
    surrogate_cycle_rates: dict[str, float] = {}
    null_gap_distributions: dict[str, dict] = {}
    for name, factory in null_specs:
        gaps: list[float] = []
        rates: list[float] = []
        for d in range(n_draws):
            seed = p.seed + null_seed_base[name] + d
            sur = factory(seed)
            gap, rate, _ = _future_er_gap_cycle_vs_global(
                sur, cycle_params, horizon=p.horizon, stride=stride
            )
            rates.append(rate)
            if gap is not None:
                gaps.append(gap)
        surrogate_cycle_rates[name] = sum(rates) / len(rates) if rates else 0.0
        n_gaps = len(gaps)
        null_gap_distributions[name] = {
            "n_draws": n_draws,
            "n_gaps": n_gaps,
            "gaps_mean": _mean(gaps),
            "observed_gap_percentile": (
                _percentile_of(observed_gap, gaps) if observed_gap is not None else None
            ),
            # P1 — resolution of the empirical percentile (Laplace-style).
            "percentile_resolution": 1.0 / (n_gaps + 1),
        }

    return {
        "ok": True,
        "kind": "regime_filter_study",
        "n_bars": n,
        "n_scored": n_scored,
        "horizon": p.horizon,
        "window": p.window,
        "null_draws": n_draws,
        "stride": stride,
        "series_cycle_rate": series_cycle_rate,
        "future_er_by_regime": regime_future_er,
        "er_gap_cycle_minus_global": observed_gap,
        "surrogate_cycle_rates": surrogate_cycle_rates,
        "null_er_gap_distributions": null_gap_distributions,
        "verdict": {
            "promote_to_decision": False,
            "note": (
                "Independent future ER target (not engine self-prediction). "
                "er_gap_cycle_minus_global vs null_er_gap_distributions percentiles; "
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
