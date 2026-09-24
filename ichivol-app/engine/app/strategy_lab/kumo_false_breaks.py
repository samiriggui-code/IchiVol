"""T12d — kumo (cloud) breakouts labeled continuation vs failure at N bars.

Lab observation only. Rising-edge ``kumo_breakout_*`` events are classified
at an explicit horizon ``N``, then sliced by RVOL band, ADX regime, structure
bias, location, and CVD bias at the breakout bar.

**Outcome (bullish breakout)**  
- ``continuation`` : still ``price_above_kumo`` at ``i+N``  
- ``failure`` : ``price_below_kumo`` at ``i+N`` (retour sous le nuage)  
- ``inside`` : prix dans le nuage à ``i+N`` (ni continuation nette ni échec franc)  
- ``incomplete`` : ``i+N`` hors série  

Bearish = miroir (``price_below_kumo`` = continuation).
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any, Literal, Sequence

from app.indicators.ichimoku import Candle
from app.strategy_lab.features import FeatureBar, FeatureSeries, build_feature_series

BreakSide = Literal["bullish", "bearish"]
BreakOutcome = Literal["continuation", "failure", "inside", "incomplete"]

DEFAULT_HORIZON_N = 5

SLICE_DIMS = (
    "rvol_band",
    "adx_regime",
    "structure",
    "location",
    "cvd",
)


def _rvol_band(bar: FeatureBar) -> str:
    if bar.rvol_faible:
        return "faible"
    if bar.rvol_normal:
        return "normal"
    if bar.rvol_eleve:
        return "eleve"
    if bar.rvol_fort:
        return "fort"
    if bar.rvol_extreme:
        return "extreme"
    return "unknown"


def _adx_regime(bar: FeatureBar) -> str:
    if bar.regime_trending:
        return "trending"
    if bar.regime_ranging:
        return "ranging"
    return "unknown"


def _structure(bar: FeatureBar) -> str:
    if bar.structure_bias_bullish:
        return "bull"
    if bar.structure_bias_bearish:
        return "bear"
    return "neutral"


def _location(bar: FeatureBar) -> str:
    if bar.wrong_side_value_area:
        return "wrong_side_va"
    if bar.beyond_value_area:
        return "beyond_va"
    if bar.inside_value_area:
        return "inside_va"
    if bar.above_vwap:
        return "above_vwap"
    if bar.below_vwap:
        return "below_vwap"
    if bar.congestion_hvn:
        return "congestion_hvn"
    return "unknown"


def _cvd(bar: FeatureBar) -> str:
    raw = (bar.cvd_bias or "UNKNOWN").upper()
    if raw in ("BUY", "SELL", "BALANCED", "UNKNOWN"):
        return raw.lower() if raw != "UNKNOWN" else "unknown"
    return "unknown"


def context_tags(bar: FeatureBar) -> dict[str, str]:
    return {
        "rvol_band": _rvol_band(bar),
        "adx_regime": _adx_regime(bar),
        "structure": _structure(bar),
        "location": _location(bar),
        "cvd": _cvd(bar),
    }


def _classify_at_horizon(
    side: BreakSide,
    future: FeatureBar | None,
) -> BreakOutcome:
    if future is None:
        return "incomplete"
    if side == "bullish":
        if future.price_above_kumo:
            return "continuation"
        if future.price_below_kumo:
            return "failure"
        return "inside"
    if future.price_below_kumo:
        return "continuation"
    if future.price_above_kumo:
        return "failure"
    return "inside"


@dataclass(frozen=True)
class KumoBreakEvent:
    index: int
    time: int
    side: BreakSide
    horizon_n: int
    outcome: BreakOutcome
    outcome_index: int | None
    context: dict[str, str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "index": self.index,
            "time": self.time,
            "side": self.side,
            "horizon_n": self.horizon_n,
            "outcome": self.outcome,
            "outcome_index": self.outcome_index,
            "context": dict(self.context),
        }


@dataclass(frozen=True)
class KumoFalseBreakReport:
    symbol: str
    timeframe: str
    n_bars: int
    horizon_n: int
    n_events: int
    n_continuation: int
    n_failure: int
    n_inside: int
    n_incomplete: int
    events: tuple[KumoBreakEvent, ...]
    by_side: dict[str, dict[str, int]]
    slices: dict[str, dict[str, dict[str, int]]]
    notes: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "n_bars": self.n_bars,
            "horizon_n": self.horizon_n,
            "n_events": self.n_events,
            "n_continuation": self.n_continuation,
            "n_failure": self.n_failure,
            "n_inside": self.n_inside,
            "n_incomplete": self.n_incomplete,
            "by_side": self.by_side,
            "slices": self.slices,
            "events": [e.to_dict() for e in self.events],
            "notes": list(self.notes),
        }


def _rising_edge_breaks(bars: Sequence[FeatureBar]) -> list[tuple[int, BreakSide]]:
    out: list[tuple[int, BreakSide]] = []
    prev_bull = False
    prev_bear = False
    for i, bar in enumerate(bars):
        bull = bool(bar.kumo_breakout_bullish)
        bear = bool(bar.kumo_breakout_bearish)
        if bull and not prev_bull:
            out.append((i, "bullish"))
        if bear and not prev_bear:
            out.append((i, "bearish"))
        prev_bull = bull
        prev_bear = bear
    return out


def _outcome_counts(events: Sequence[KumoBreakEvent]) -> dict[str, int]:
    c: Counter[str] = Counter(e.outcome for e in events)
    return {
        "continuation": int(c.get("continuation", 0)),
        "failure": int(c.get("failure", 0)),
        "inside": int(c.get("inside", 0)),
        "incomplete": int(c.get("incomplete", 0)),
        "n": len(events),
    }


def _build_slices(events: Sequence[KumoBreakEvent]) -> dict[str, dict[str, dict[str, int]]]:
    slices: dict[str, dict[str, dict[str, int]]] = {d: {} for d in SLICE_DIMS}
    for ev in events:
        for dim in SLICE_DIMS:
            key = ev.context.get(dim, "unknown")
            bucket = slices[dim].setdefault(
                key,
                {"continuation": 0, "failure": 0, "inside": 0, "incomplete": 0, "n": 0},
            )
            bucket[ev.outcome] += 1
            bucket["n"] += 1
    return slices


def study_kumo_false_breaks_on_features(
    features: FeatureSeries,
    *,
    horizon_n: int = DEFAULT_HORIZON_N,
    symbol: str = "",
    timeframe: str = "",
) -> KumoFalseBreakReport:
    if horizon_n < 1:
        raise ValueError("horizon_n must be >= 1")
    bars = features.bars
    n = len(bars)
    events: list[KumoBreakEvent] = []
    for idx, side in _rising_edge_breaks(bars):
        out_i = idx + horizon_n
        future = bars[out_i] if out_i < n else None
        outcome = _classify_at_horizon(side, future)
        events.append(
            KumoBreakEvent(
                index=idx,
                time=bars[idx].time,
                side=side,
                horizon_n=horizon_n,
                outcome=outcome,
                outcome_index=out_i if future is not None else None,
                context=context_tags(bars[idx]),
            )
        )

    by_side = {
        "bullish": _outcome_counts([e for e in events if e.side == "bullish"]),
        "bearish": _outcome_counts([e for e in events if e.side == "bearish"]),
        "all": _outcome_counts(events),
    }
    totals = by_side["all"]
    notes = (
        f"Horizon N={horizon_n} barres explicite (paramètre horizon_n).",
        "continuation = prix du bon côté du nuage à i+N ; failure = côté opposé.",
        "inside = prix dans le nuage à i+N ; incomplete = série trop courte.",
        "Tranches : contexte au bar de cassure (RVOL / ADX / structure / location / CVD).",
    )
    return KumoFalseBreakReport(
        symbol=symbol,
        timeframe=timeframe,
        n_bars=n,
        horizon_n=horizon_n,
        n_events=len(events),
        n_continuation=totals["continuation"],
        n_failure=totals["failure"],
        n_inside=totals["inside"],
        n_incomplete=totals["incomplete"],
        events=tuple(events),
        by_side=by_side,
        slices=_build_slices(events),
        notes=notes,
    )


def study_kumo_false_breaks_on_candles(
    candles: Sequence[Candle],
    *,
    horizon_n: int = DEFAULT_HORIZON_N,
    symbol: str = "",
    timeframe: str = "",
) -> KumoFalseBreakReport:
    features = build_feature_series(candles)
    return study_kumo_false_breaks_on_features(
        features,
        horizon_n=horizon_n,
        symbol=symbol,
        timeframe=timeframe,
    )
