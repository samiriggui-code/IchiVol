"""T-CYCLE Lab harness — causal walk-forward + null models (observe-only).

Never touches decision/pipeline. Scores period / phase / regime stability
against simple baselines. A complex engine that loses to nulls must not
be promoted.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Sequence

from app.cycle.engine import CycleParams, compute_cycle_series
from app.cycle.types import CycleRegime, CycleState
from app.indicators.ichimoku import Candle


@dataclass(frozen=True)
class CycleStudyParams:
    window: int = 96
    min_period: float = 8.0
    max_period: float = 60.0
    horizon: int = 8
    """Bars ahead used to score period persistence / phase advance."""
    seed: int = 7


def _mae(errors: list[float]) -> float | None:
    if not errors:
        return None
    return sum(abs(e) for e in errors) / len(errors)


def _median(xs: list[float]) -> float | None:
    if not xs:
        return None
    s = sorted(xs)
    m = len(s) // 2
    return s[m] if len(s) % 2 else 0.5 * (s[m - 1] + s[m])


def _phase_advance(phase: float, period: float, bars: int) -> float:
    """Expected phase fraction after `bars` if period is constant."""
    if period <= 0:
        return phase
    return (phase + bars / period) % 1.0


def _circ_delta(a: float, b: float) -> float:
    """Smallest distance on [0,1) circle."""
    d = abs(a - b) % 1.0
    return min(d, 1.0 - d)


def run_cycle_walk_forward(
    candles: Sequence[Candle],
    params: CycleStudyParams | None = None,
) -> dict:
    """Causal walk-forward on a single series.

    At each bar T (after warmup): use CycleState(T) only, then score against
    T+horizon using future bars that were *not* in the compute window for T.
    """
    p = params or CycleStudyParams()
    cycle_params = CycleParams(
        window=p.window,
        min_period=p.min_period,
        max_period=p.max_period,
    )
    states = compute_cycle_series(candles, cycle_params)
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

    rng = random.Random(p.seed)

    # Collect historical periods for null "average cycle"
    hist_periods: list[float] = []

    engine_period_err: list[float] = []
    persist_period_err: list[float] = []
    avg_period_err: list[float] = []
    random_period_err: list[float] = []

    engine_phase_err: list[float] = []
    persist_phase_err: list[float] = []
    random_phase_err: list[float] = []

    regime_counts: dict[str, int] = {r.value: 0 for r in CycleRegime}
    quality_sum = 0.0
    agreement_sum = 0.0
    n_scored = 0
    n_with_period = 0

    for i in range(min_i, max_i + 1):
        st: CycleState = states[i]
        future: CycleState = states[i + p.horizon]
        regime_counts[st.regime.value] = regime_counts.get(st.regime.value, 0) + 1
        quality_sum += st.quality
        agreement_sum += st.methods_agreement
        n_scored += 1

        if st.dominant_period_candles is not None:
            hist_periods.append(st.dominant_period_candles)

        if (
            st.dominant_period_candles is None
            or future.dominant_period_candles is None
        ):
            continue
        n_with_period += 1
        true_p = future.dominant_period_candles
        eng_p = st.dominant_period_candles
        engine_period_err.append(eng_p - true_p)

        # Null: previous-cycle persistence (= engine period held constant — same
        # as eng_p here; use lag-1 if available for a distinct baseline)
        prev_p = (
            states[i - 1].dominant_period_candles
            if i > 0 and states[i - 1].dominant_period_candles is not None
            else eng_p
        )
        persist_period_err.append(prev_p - true_p)

        avg_p = sum(hist_periods) / len(hist_periods) if hist_periods else eng_p
        avg_period_err.append(avg_p - true_p)

        rnd_p = rng.uniform(p.min_period, p.max_period)
        random_period_err.append(rnd_p - true_p)

        if st.phase is not None and future.phase is not None and eng_p > 0:
            pred_phase = _phase_advance(st.phase, eng_p, p.horizon)
            engine_phase_err.append(_circ_delta(pred_phase, future.phase))
            # Null persist: phase unchanged
            persist_phase_err.append(_circ_delta(st.phase, future.phase))
            random_phase_err.append(_circ_delta(rng.random(), future.phase))

    def _pack(errors: list[float]) -> dict:
        return {
            "n": len(errors),
            "mae": _mae(errors),
            "median_abs": _median([abs(e) for e in errors]),
        }

    engine_period_mae = _mae(engine_period_err)
    null_best_period_mae = None
    for candidate in (
        _mae(persist_period_err),
        _mae(avg_period_err),
        _mae(random_period_err),
    ):
        if candidate is None:
            continue
        if null_best_period_mae is None or candidate < null_best_period_mae:
            null_best_period_mae = candidate

    beats_period_nulls = (
        engine_period_mae is not None
        and null_best_period_mae is not None
        and engine_period_mae < null_best_period_mae
    )

    engine_phase_mae = _mae(engine_phase_err)
    null_best_phase_mae = None
    for candidate in (_mae(persist_phase_err), _mae(random_phase_err)):
        if candidate is None:
            continue
        if null_best_phase_mae is None or candidate < null_best_phase_mae:
            null_best_phase_mae = candidate
    beats_phase_nulls = (
        engine_phase_mae is not None
        and null_best_phase_mae is not None
        and engine_phase_mae < null_best_phase_mae
    )

    return {
        "ok": True,
        "n_bars": n,
        "n_scored": n_scored,
        "n_with_period": n_with_period,
        "horizon": p.horizon,
        "window": p.window,
        "regime_counts": regime_counts,
        "mean_quality": quality_sum / n_scored if n_scored else None,
        "mean_agreement": agreement_sum / n_scored if n_scored else None,
        "period": {
            "engine": _pack(engine_period_err),
            "null_persist": _pack(persist_period_err),
            "null_historical_avg": _pack(avg_period_err),
            "null_random": _pack(random_period_err),
            "beats_best_null": beats_period_nulls,
        },
        "phase": {
            "engine_advance": _pack(engine_phase_err),
            "null_persist": _pack(persist_phase_err),
            "null_random": _pack(random_phase_err),
            "beats_best_null": beats_phase_nulls,
        },
        "verdict": {
            "period_useful": beats_period_nulls,
            "phase_useful": beats_phase_nulls,
            "promote_to_decision": False,
            "note": (
                "Research only. promote_to_decision stays false until multi-symbol "
                "OOS + ablation A–G pass. beats_* compare MAE only on this series."
            ),
        },
    }
