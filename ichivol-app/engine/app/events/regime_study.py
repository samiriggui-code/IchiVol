"""PHASE 6 — stratify Strategy Lab event-study by EventAnomaly market regime.

Research-only. Does NOT change pipeline gates or BUY/SELL. Answers:
"what happens to PIPELINE entries when the bar is NORMAL_MARKET vs
UNKNOWN_EVENT (anomaly without news match)?"

Uses the same observe_event / aggregate_events path as regime_slices.py.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Sequence

from app.agents.types import Direction
from app.backtest.experiments import PIPELINE, prepare_variants
from app.events.anomaly import detect_anomaly
from app.events.thresholds import AnomalyThresholds, DEFAULT_THRESHOLDS
from app.events.types import MarketRegime
from app.indicators.atr import AtrState
from app.indicators.ichimoku import Candle
from app.indicators.registry import REGISTRY
from app.strategy_lab.event_study import (
    DEFAULT_HORIZONS,
    EventObservation,
    EventStudyResult,
    aggregate_events,
    extract_entry_signals,
    event_study_dict,
    observe_event,
)

REGIME_SLICE_ORDER = (
    "GLOBAL",
    MarketRegime.NORMAL_MARKET.value,
    MarketRegime.UNKNOWN_EVENT.value,
    MarketRegime.EVENT_MARKET.value,
)


@dataclass(frozen=True)
class AnomalyRegimeSlice:
    regime: str
    n_signals: int
    study: EventStudyResult


@dataclass(frozen=True)
class AnomalyRegimeStudyReport:
    """Comparison of PIPELINE entries stratified by anomaly regime at signal time."""

    symbol: str
    timeframe: str
    variant: str
    n_bars: int
    feature_version: str
    slices: list[AnomalyRegimeSlice] = field(default_factory=list)
    regime_bar_counts: dict[str, int] = field(default_factory=dict)
    comparison: dict[str, object] = field(default_factory=dict)
    """Derived deltas NORMAL vs UNKNOWN (null-safe) — never a trading rule."""


def tag_bars_by_anomaly(
    candles: Sequence[Candle],
    *,
    symbol: str,
    timeframe: str,
    atr_states: Sequence[AtrState],
    rvol_values: Sequence[float | None] | None = None,
    thresholds: AnomalyThresholds | None = None,
) -> list[MarketRegime]:
    """Causal per-bar regime: detect_anomaly on candles[0..i] for each i."""
    thr = thresholds or DEFAULT_THRESHOLDS
    out: list[MarketRegime] = []
    for i in range(len(candles)):
        atr = atr_states[i].atr if i < len(atr_states) and atr_states[i].atr else None
        rvol = None
        if rvol_values is not None and i < len(rvol_values):
            rvol = rvol_values[i]
        obs = detect_anomaly(
            candles[: i + 1],
            symbol=symbol,
            timeframe=timeframe,
            rvol=rvol,
            atr=float(atr) if atr else None,
            thresholds=thr,
        )
        out.append(obs.market_regime)
    return out


def _filter_signals(
    signals: Sequence[tuple[int, Direction]],
    regimes: Sequence[MarketRegime],
    label: str,
) -> list[tuple[int, Direction]]:
    if label == "GLOBAL":
        return list(signals)
    return [(i, d) for i, d in signals if i < len(regimes) and regimes[i].value == label]


def _observe_filtered(
    candles: Sequence[Candle],
    atr_states: Sequence[AtrState],
    signals: Sequence[tuple[int, Direction]],
    horizons: Sequence[int],
    r_multiple: float,
) -> list[EventObservation]:
    events: list[EventObservation] = []
    for idx, direction in signals:
        atr = atr_states[idx].atr if idx < len(atr_states) else None
        if atr is None or atr <= 0:
            continue
        ev = observe_event(
            candles, idx, direction, float(atr), horizons, r_multiple=r_multiple
        )
        if ev is not None:
            events.append(ev)
    return events


def _comparison_block(slices: list[AnomalyRegimeSlice]) -> dict[str, object]:
    by = {s.regime: s for s in slices}
    normal = by.get(MarketRegime.NORMAL_MARKET.value)
    unknown = by.get(MarketRegime.UNKNOWN_EVENT.value)
    out: dict[str, object] = {
        "note": (
            "Observational only — do not change gates from these deltas "
            "without a calibrated sample and product review."
        ),
    }
    if not normal or not unknown or normal.n_signals == 0 or unknown.n_signals == 0:
        out["available"] = False
        return out
    out["available"] = True
    out["n_normal"] = normal.n_signals
    out["n_unknown_event"] = unknown.n_signals

    def delta(a: float | None, b: float | None) -> float | None:
        if a is None or b is None:
            return None
        return float(b - a)

    out["delta_mean_mfe_atr_unknown_minus_normal"] = delta(
        normal.study.mean_mfe_atr, unknown.study.mean_mfe_atr
    )
    out["delta_mean_mae_atr_unknown_minus_normal"] = delta(
        normal.study.mean_mae_atr, unknown.study.mean_mae_atr
    )
    out["delta_pct_hit_r_unknown_minus_normal"] = delta(
        normal.study.pct_hit_plus_r_before_minus_r,
        unknown.study.pct_hit_plus_r_before_minus_r,
    )
    # Horizon 5 ATR mean if present
    def h_mean(study: EventStudyResult, h: int) -> float | None:
        for hs in study.horizon_stats:
            if hs.horizon == h:
                return hs.mean_atr
        return None

    out["delta_h5_mean_atr_unknown_minus_normal"] = delta(
        h_mean(normal.study, 5), h_mean(unknown.study, 5)
    )
    return out


def study_anomaly_regimes(
    candles: Sequence[Candle],
    desired: Sequence[Direction],
    atr_states: Sequence[AtrState],
    *,
    symbol: str,
    timeframe: str,
    variant: str = PIPELINE,
    horizons: Sequence[int] = DEFAULT_HORIZONS,
    r_multiple: float = 1.0,
    thresholds: AnomalyThresholds | None = None,
    rvol_values: Sequence[float | None] | None = None,
    min_signals: int = 5,
) -> AnomalyRegimeStudyReport:
    """Stratify PIPELINE (or any desired series) entries by anomaly regime."""
    thr = thresholds or DEFAULT_THRESHOLDS
    if rvol_values is None:
        rvol_states = REGISTRY.compute("rvol", list(candles))
        rvol_values = [s.rvol for s in rvol_states]

    regimes = tag_bars_by_anomaly(
        candles,
        symbol=symbol,
        timeframe=timeframe,
        atr_states=atr_states,
        rvol_values=rvol_values,
        thresholds=thr,
    )
    counts: dict[str, int] = {}
    for r in regimes:
        counts[r.value] = counts.get(r.value, 0) + 1

    signals = extract_entry_signals(desired)
    slices: list[AnomalyRegimeSlice] = []
    labels = list(REGIME_SLICE_ORDER)
    for lab in counts:
        if lab not in labels:
            labels.append(lab)

    for label in labels:
        filtered = _filter_signals(signals, regimes, label)
        if label != "GLOBAL" and len(filtered) < min_signals and label not in (
            MarketRegime.NORMAL_MARKET.value,
            MarketRegime.UNKNOWN_EVENT.value,
            "GLOBAL",
        ):
            # Keep NORMAL/UNKNOWN/GLOBAL even if thin (report n=0/small honestly).
            if len(filtered) == 0 and label not in (
                MarketRegime.NORMAL_MARKET.value,
                MarketRegime.UNKNOWN_EVENT.value,
                "GLOBAL",
            ):
                continue
        events = _observe_filtered(candles, atr_states, filtered, horizons, r_multiple)
        study = aggregate_events(
            events,
            horizons,
            r_multiple,
            symbol=symbol,
            timeframe=timeframe,
            variant=f"{variant}|anomaly_regime={label}",
            n_bars=len(candles),
        )
        slices.append(AnomalyRegimeSlice(regime=label, n_signals=len(events), study=study))

    return AnomalyRegimeStudyReport(
        symbol=symbol,
        timeframe=timeframe,
        variant=variant,
        n_bars=len(candles),
        feature_version=thr.feature_version,
        slices=slices,
        regime_bar_counts=counts,
        comparison=_comparison_block(slices),
    )


def run_anomaly_regime_study(
    symbol: str,
    timeframe: str = "1h",
    limit: int = 1000,
    *,
    horizons: Sequence[int] = DEFAULT_HORIZONS,
    r_multiple: float = 1.0,
    exchange: str = "binance",
    thresholds: AnomalyThresholds | None = None,
    min_signals: int = 5,
) -> AnomalyRegimeStudyReport:
    """Fetch PIPELINE series and stratify event-study by anomaly regime."""
    prepared = prepare_variants(symbol, timeframe=timeframe, limit=limit, exchange=exchange)
    desired = prepared.positions[PIPELINE]
    return study_anomaly_regimes(
        prepared.candles,
        desired,
        prepared.atr_states,
        symbol=symbol,
        timeframe=timeframe,
        variant=PIPELINE,
        horizons=horizons,
        r_multiple=r_multiple,
        thresholds=thresholds,
        min_signals=min_signals,
    )


def anomaly_regime_study_dict(report: AnomalyRegimeStudyReport) -> dict:
    return {
        "symbol": report.symbol,
        "timeframe": report.timeframe,
        "variant": report.variant,
        "n_bars": report.n_bars,
        "feature_version": report.feature_version,
        "regime_bar_counts": report.regime_bar_counts,
        "comparison": report.comparison,
        "disclaimer": (
            "Scénarios / régimes d'anomalie — mesure empirique, pas une règle de trading."
        ),
        "slices": [
            {
                "regime": s.regime,
                "n_signals": s.n_signals,
                "study": event_study_dict(s.study, include_events=False),
            }
            for s in report.slices
        ],
    }
