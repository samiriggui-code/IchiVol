"""T5b — historical family-weight profile study (observation-only).

At each bar where the staged pipeline would emit BUY/SELL, record
``weighted_support`` under every named profile and optional forward
log returns. Never changes fills, gates, or live confidence.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Sequence

from app.agents import ichimoku_agent, rvol_agent
from app.confluence.observe import observe_family_weights
from app.confluence.profiles import FAMILY_WEIGHT_PROFILES, FamilyWeightProfile
from app.decision.pipeline import build_pipeline
from app.indicators.ichimoku import Candle, IchimokuParams
from app.indicators.registry import REGISTRY
from app.indicators.rvol import RvolParams

DEFAULT_HORIZONS = (1, 3, 5, 10)
_ACTIONABLE = frozenset({"BUY", "SELL"})


@dataclass(frozen=True)
class ProfileSignalRow:
    bar_index: int
    time: int
    pipeline_decision: str
    direction: str
    supports: dict[str, float]  # profile_id → weighted_support
    forward_log_returns: dict[str, float | None]  # "h1" → float|None


@dataclass(frozen=True)
class ProfileAggregate:
    profile_id: str
    n_signals: int
    mean_support: float
    mean_forward: dict[str, float | None]  # horizon key → mean log ret


@dataclass(frozen=True)
class FamilyWeightsStudyReport:
    symbol: str
    timeframe: str
    n_bars: int
    n_signals: int
    horizons: list[int]
    profile_ids: list[str]
    aggregates: list[ProfileAggregate] = field(default_factory=list)
    sample: list[ProfileSignalRow] = field(default_factory=list)
    disclaimer: str = (
        "Family weights study — observation only; does not alter decision, "
        "confidence, fills, or gates."
    )

    def to_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "n_bars": self.n_bars,
            "n_signals": self.n_signals,
            "horizons": list(self.horizons),
            "profile_ids": list(self.profile_ids),
            "aggregates": [
                {
                    "profile_id": a.profile_id,
                    "n_signals": a.n_signals,
                    "mean_support": a.mean_support,
                    "mean_forward": a.mean_forward,
                }
                for a in self.aggregates
            ],
            "sample": [
                {
                    "bar_index": s.bar_index,
                    "time": s.time,
                    "pipeline_decision": s.pipeline_decision,
                    "direction": s.direction,
                    "supports": s.supports,
                    "forward_log_returns": s.forward_log_returns,
                }
                for s in self.sample
            ],
            "disclaimer": self.disclaimer,
        }


def _forward_log_returns(
    candles: Sequence[Candle],
    i: int,
    direction: str,
    horizons: Sequence[int],
) -> dict[str, float | None]:
    out: dict[str, float | None] = {}
    entry = candles[i].close
    if entry <= 0:
        return {f"h{h}": None for h in horizons}
    sign = 1.0 if direction == "LONG" else -1.0
    for h in horizons:
        j = i + h
        if j >= len(candles) or candles[j].close <= 0:
            out[f"h{h}"] = None
        else:
            out[f"h{h}"] = sign * math.log(candles[j].close / entry)
    return out


def run_family_weights_study(
    candles: Sequence[Candle],
    *,
    symbol: str,
    timeframe: str,
    profiles: dict[str, FamilyWeightProfile] | None = None,
    horizons: Sequence[int] = DEFAULT_HORIZONS,
    ichi_params: IchimokuParams = IchimokuParams(),
    rvol_params: RvolParams = RvolParams(),
    step: int = 1,
    sample_limit: int = 20,
    min_bars: int = 80,
) -> FamilyWeightsStudyReport:
    """Causal prefix study: pipeline at bar i uses only candles[0..i]."""
    catalog = profiles or FAMILY_WEIGHT_PROFILES
    profile_ids = list(catalog.keys())
    n = len(candles)
    if n < min_bars:
        return FamilyWeightsStudyReport(
            symbol=symbol,
            timeframe=timeframe,
            n_bars=n,
            n_signals=0,
            horizons=list(horizons),
            profile_ids=profile_ids,
        )

    # Full-series agents/indicators (each state[i] is causal for bar i).
    ichi_series = ichimoku_agent.analyze(list(candles), ichi_params)
    rvol_series = rvol_agent.analyze(list(candles), rvol_params)
    computed = REGISTRY.compute_many(
        ["structure", "atr", "location", "cvd", "adx", "donchian"],
        list(candles),
    )

    rows: list[ProfileSignalRow] = []
    support_sums: dict[str, float] = {pid: 0.0 for pid in profile_ids}
    support_counts: dict[str, int] = {pid: 0 for pid in profile_ids}
    fwd_sums: dict[str, dict[str, float]] = {
        pid: {f"h{h}": 0.0 for h in horizons} for pid in profile_ids
    }
    fwd_counts: dict[str, dict[str, int]] = {
        pid: {f"h{h}": 0 for h in horizons} for pid in profile_ids
    }

    start = max(min_bars - 1, 0)
    for i in range(start, n, max(1, step)):
        pipe = build_pipeline(
            ichimoku=ichi_series[i],
            rvol=rvol_series[i],
            structure=computed["structure"][i],
            atr=computed["atr"][i],
            location=computed["location"][i],
            cvd=computed["cvd"][i],
            adx=computed["adx"][i],
            donchian=computed["donchian"][i],
        )
        if pipe.decision not in _ACTIONABLE:
            continue
        supports: dict[str, float] = {}
        for pid, profile in catalog.items():
            obs = observe_family_weights(pipe, profile.config)
            supports[pid] = obs.weighted_support
            support_sums[pid] += obs.weighted_support
            support_counts[pid] += 1
        fwd = _forward_log_returns(
            candles, i, pipe.direction.value, horizons
        )
        for pid in profile_ids:
            for key, val in fwd.items():
                if val is not None:
                    fwd_sums[pid][key] += val
                    fwd_counts[pid][key] += 1
        rows.append(
            ProfileSignalRow(
                bar_index=i,
                time=int(candles[i].time),
                pipeline_decision=pipe.decision,
                direction=pipe.direction.value,
                supports=supports,
                forward_log_returns=fwd,
            )
        )

    aggregates: list[ProfileAggregate] = []
    for pid in profile_ids:
        n_sig = support_counts[pid]
        mean_fwd: dict[str, float | None] = {}
        for key in (f"h{h}" for h in horizons):
            c = fwd_counts[pid][key]
            mean_fwd[key] = (fwd_sums[pid][key] / c) if c else None
        aggregates.append(
            ProfileAggregate(
                profile_id=pid,
                n_signals=n_sig,
                mean_support=(support_sums[pid] / n_sig) if n_sig else 0.0,
                mean_forward=mean_fwd,
            )
        )

    return FamilyWeightsStudyReport(
        symbol=symbol,
        timeframe=timeframe,
        n_bars=n,
        n_signals=len(rows),
        horizons=list(horizons),
        profile_ids=profile_ids,
        aggregates=aggregates,
        sample=rows[:sample_limit],
    )


# Observation study exports.
__all__ = [
    "FamilyWeightsStudyReport",
    "run_family_weights_study",
]
