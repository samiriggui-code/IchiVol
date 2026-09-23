"""PHASE 6 — empirical threshold suggestions (past-only quantiles).

Does NOT mutate DEFAULT_THRESHOLDS. Produces suggested gates from a causal
feature series so humans/Claude can review before promoting a new
``event_anomaly_vN`` version.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence

from app.events.anomaly import detect_anomaly
from app.events.thresholds import AnomalyThresholds, DEFAULT_THRESHOLDS, EVENT_ANOMALY_FEATURE_VERSION
from app.indicators.atr import AtrState
from app.indicators.ichimoku import Candle
from app.indicators.registry import REGISTRY


@dataclass(frozen=True)
class FeatureQuantiles:
    name: str
    n: int
    p90: float | None
    p95: float | None
    p99: float | None
    p995: float | None


@dataclass(frozen=True)
class CalibrationReport:
    symbol: str
    timeframe: str
    n_bars: int
    feature_version_baseline: str
    quantiles: list[FeatureQuantiles]
    suggested_thresholds: dict[str, float]
    note: str


def _quantile(sorted_vals: Sequence[float], q: float) -> float | None:
    if not sorted_vals:
        return None
    if q <= 0:
        return float(sorted_vals[0])
    if q >= 1:
        return float(sorted_vals[-1])
    pos = q * (len(sorted_vals) - 1)
    lo = int(math.floor(pos))
    hi = int(math.ceil(pos))
    if lo == hi:
        return float(sorted_vals[lo])
    w = pos - lo
    return float(sorted_vals[lo] * (1 - w) + sorted_vals[hi] * w)


def _pack(name: str, vals: list[float]) -> FeatureQuantiles:
    s = sorted(v for v in vals if math.isfinite(v))
    return FeatureQuantiles(
        name=name,
        n=len(s),
        p90=_quantile(s, 0.90),
        p95=_quantile(s, 0.95),
        p99=_quantile(s, 0.99),
        p995=_quantile(s, 0.995),
    )


def calibrate_anomaly_thresholds(
    candles: Sequence[Candle],
    atr_states: Sequence[AtrState],
    *,
    symbol: str,
    timeframe: str,
    thresholds: AnomalyThresholds | None = None,
) -> CalibrationReport:
    """Walk bars causally; collect feature magnitudes; suggest p99 gates."""
    thr = thresholds or DEFAULT_THRESHOLDS
    rvol_states = REGISTRY.compute("rvol", list(candles))
    abs_ret_z: list[float] = []
    vol_z: list[float] = []
    abs_vola_z: list[float] = []
    range_atr: list[float] = []
    gap_atr: list[float] = []
    rvols: list[float] = []

    warm = thr.min_history
    for i in range(warm, len(candles)):
        atr = atr_states[i].atr if i < len(atr_states) else None
        rvol = rvol_states[i].rvol if i < len(rvol_states) else None
        obs = detect_anomaly(
            candles[: i + 1],
            symbol=symbol,
            timeframe=timeframe,
            rvol=float(rvol) if rvol is not None else None,
            atr=float(atr) if atr else None,
            thresholds=thr,
        )
        if obs.return_zscore is not None:
            abs_ret_z.append(abs(obs.return_zscore))
        if obs.volume_zscore is not None:
            vol_z.append(obs.volume_zscore)
        if obs.volatility_zscore is not None:
            abs_vola_z.append(abs(obs.volatility_zscore))
        if obs.range_atr_ratio is not None:
            range_atr.append(obs.range_atr_ratio)
        if obs.gap_atr_ratio is not None:
            gap_atr.append(obs.gap_atr_ratio)
        if obs.rvol is not None:
            rvols.append(obs.rvol)

    packs = [
        _pack("abs_return_z", abs_ret_z),
        _pack("volume_z", vol_z),
        _pack("abs_volatility_z", abs_vola_z),
        _pack("range_atr", range_atr),
        _pack("gap_atr", gap_atr),
        _pack("rvol", rvols),
    ]
    by_name = {p.name: p for p in packs}
    suggested = {
        "return_z_abs": by_name["abs_return_z"].p99 or thr.return_z_abs,
        "volume_z": by_name["volume_z"].p99 or thr.volume_z,
        "volatility_z_abs": by_name["abs_volatility_z"].p99 or thr.volatility_z_abs,
        "range_atr": by_name["range_atr"].p99 or thr.range_atr,
        "gap_atr": by_name["gap_atr"].p99 or thr.gap_atr,
        "rvol": by_name["rvol"].p99 or thr.rvol,
    }
    return CalibrationReport(
        symbol=symbol,
        timeframe=timeframe,
        n_bars=len(candles),
        feature_version_baseline=EVENT_ANOMALY_FEATURE_VERSION,
        quantiles=packs,
        suggested_thresholds={k: float(v) for k, v in suggested.items()},
        note=(
            "Suggestions = empirical p99 on this window (causal). "
            "Do not promote without walk-forward validation and a new feature_version."
        ),
    )


def calibration_report_dict(report: CalibrationReport) -> dict:
    return {
        "symbol": report.symbol,
        "timeframe": report.timeframe,
        "n_bars": report.n_bars,
        "feature_version_baseline": report.feature_version_baseline,
        "note": report.note,
        "suggested_thresholds": report.suggested_thresholds,
        "quantiles": [
            {
                "name": q.name,
                "n": q.n,
                "p90": q.p90,
                "p95": q.p95,
                "p99": q.p99,
                "p995": q.p995,
            }
            for q in report.quantiles
        ],
    }
