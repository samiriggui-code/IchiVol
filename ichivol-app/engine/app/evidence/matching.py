"""Historical matching — simple, explainable similarity on SignalContext.

No deep learning. Match on asset class, timeframe, regime, Ichimoku state,
RVOL band, ATR percentile band, structure bias. Returns observation counts
and forward-return distributions when enough history exists; otherwise
INSUFFICIENT_EVIDENCE.
"""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass, field
from typing import Any, Sequence

from app.evidence.context import SignalContext
from app.evidence.sample import SampleQuality, classify_sample
from app.indicators.ichimoku import Candle

DEFAULT_HORIZONS = (1, 3, 5, 10, 20)


@dataclass(frozen=True)
class MatchCriteria:
    """Which context dimensions must agree for a historical match."""

    same_asset_class: bool = True
    same_timeframe: bool = True
    same_ichimoku_direction: bool = True
    same_price_vs_cloud: bool = True
    same_tk_state_family: bool = True  # BULLISH/BEARISH/NONE buckets
    same_structure_trend: bool = True
    same_regime_status: bool = True
    rvol_band: bool = True
    atr_percentile_band: bool = True
    same_volume_type: bool = True


@dataclass(frozen=True)
class ForwardPath:
    horizon: int
    return_pct: float | None
    mfe_pct: float | None
    mae_pct: float | None


@dataclass(frozen=True)
class HistoricalMatch:
    context: SignalContext
    forward: list[ForwardPath]
    """Signed returns assuming the query context's confluence direction
    (LONG → positive when price rises; SHORT inverted)."""


@dataclass(frozen=True)
class MatchStats:
    sample_size: int
    sample_quality: SampleQuality
    status: str
    """VALID | INSUFFICIENT_EVIDENCE | NO_DATA"""
    mean_return_pct: float | None
    median_return_pct: float | None
    favorable_rate: float | None
    mean_mfe_pct: float | None
    mean_mae_pct: float | None
    horizon: int
    matches: list[HistoricalMatch] = field(default_factory=list, repr=False)


def _tk_family(tk_state: str | None) -> str:
    if not tk_state:
        return "NONE"
    u = tk_state.upper()
    if "BULL" in u:
        return "BULLISH"
    if "BEAR" in u:
        return "BEARISH"
    return "NONE"


def _rvol_band(rvol: float | None) -> str:
    if rvol is None or math.isnan(rvol):
        return "UNKNOWN"
    if rvol < 0.8:
        return "LOW"
    if rvol < 1.5:
        return "SUB_THRESHOLD"
    if rvol < 2.5:
        return "CONFIRMED"
    return "HIGH"


def _atr_band(pct: float | None) -> str:
    if pct is None or math.isnan(pct):
        return "UNKNOWN"
    if pct < 0.2:
        return "DEAD"
    if pct < 0.8:
        return "NORMAL"
    return "EXTREME"


def contexts_match(query: SignalContext, candidate: SignalContext, criteria: MatchCriteria) -> bool:
    if query.feature_version != candidate.feature_version:
        return False
    if criteria.same_asset_class and query.asset_class != candidate.asset_class:
        return False
    if criteria.same_timeframe and query.timeframe != candidate.timeframe:
        return False
    if criteria.same_volume_type:
        qv = query.volume.volume_type if query.volume else None
        cv = candidate.volume.volume_type if candidate.volume else None
        if qv != cv:
            return False

    if criteria.same_ichimoku_direction:
        qd = query.ichimoku.direction if query.ichimoku else None
        cd = candidate.ichimoku.direction if candidate.ichimoku else None
        if qd != cd:
            return False
    if criteria.same_price_vs_cloud:
        qp = query.ichimoku.price_vs_cloud if query.ichimoku else None
        cp = candidate.ichimoku.price_vs_cloud if candidate.ichimoku else None
        if qp != cp:
            return False
    if criteria.same_tk_state_family:
        qt = _tk_family(query.ichimoku.tk_state if query.ichimoku else None)
        ct = _tk_family(candidate.ichimoku.tk_state if candidate.ichimoku else None)
        if qt != ct:
            return False

    if criteria.same_structure_trend:
        qs = query.structure.trend if query.structure else None
        cs = candidate.structure.trend if candidate.structure else None
        if qs is not None and cs is not None and qs != cs:
            return False

    if criteria.same_regime_status:
        qr = query.regime.pipeline_regime if query.regime else None
        cr = candidate.regime.pipeline_regime if candidate.regime else None
        if qr is not None and cr is not None and qr != cr:
            return False

    if criteria.rvol_band:
        qb = _rvol_band(query.volume.rvol if query.volume else None)
        cb = _rvol_band(candidate.volume.rvol if candidate.volume else None)
        if qb != cb:
            return False

    if criteria.atr_percentile_band:
        qa = _atr_band(query.volatility.atr_percentile if query.volatility else None)
        ca = _atr_band(candidate.volatility.atr_percentile if candidate.volatility else None)
        if qa != "UNKNOWN" and ca != "UNKNOWN" and qa != ca:
            return False

    return True


def _signed_return(entry: float, exit_px: float, direction: str) -> float:
    raw = (exit_px - entry) / entry if entry else 0.0
    return raw if direction == "LONG" else -raw


def _path_metrics(
    candles: Sequence[Candle],
    signal_idx: int,
    direction: str,
    horizons: Sequence[int],
) -> list[ForwardPath]:
    """Anti-lookahead: entry = open of bar signal_idx+1; scan only future bars."""
    entry_idx = signal_idx + 1
    if entry_idx >= len(candles):
        return [ForwardPath(h, None, None, None) for h in horizons]
    entry = candles[entry_idx].open
    out: list[ForwardPath] = []
    for h in horizons:
        end = entry_idx + h - 1
        if end >= len(candles) or entry <= 0:
            out.append(ForwardPath(h, None, None, None))
            continue
        window = candles[entry_idx : end + 1]
        ret = _signed_return(entry, candles[end].close, direction)
        if direction == "LONG":
            mfe = max((c.high - entry) / entry for c in window)
            mae = max((entry - c.low) / entry for c in window)
        else:
            mfe = max((entry - c.low) / entry for c in window)
            mae = max((c.high - entry) / entry for c in window)
        out.append(ForwardPath(h, ret, mfe, mae))
    return out


def match_historical(
    query: SignalContext,
    catalog: Sequence[tuple[SignalContext, Sequence[Candle], int]],
    *,
    criteria: MatchCriteria = MatchCriteria(),
    horizons: Sequence[int] = DEFAULT_HORIZONS,
    primary_horizon: int = 10,
    exclude_same_timestamp: bool = True,
) -> MatchStats:
    """Search catalog of (context, candles, signal_index) for similar setups.

    `catalog` entries must use candles that extend past the signal index so
    forward paths can be measured. Never fabricates outcomes.
    """
    direction = (
        query.confluence.direction
        if query.confluence and query.confluence.direction in ("LONG", "SHORT")
        else (query.ichimoku.direction if query.ichimoku else "NEUTRAL")
    )
    if direction == "NEUTRAL":
        return MatchStats(
            sample_size=0,
            sample_quality=SampleQuality.NO_DATA,
            status="NO_DATA",
            mean_return_pct=None,
            median_return_pct=None,
            favorable_rate=None,
            mean_mfe_pct=None,
            mean_mae_pct=None,
            horizon=primary_horizon,
        )

    matches: list[HistoricalMatch] = []
    for ctx, candles, idx in catalog:
        if exclude_same_timestamp and ctx.timestamp == query.timestamp and ctx.symbol == query.symbol:
            continue
        if not contexts_match(query, ctx, criteria):
            continue
        forward = _path_metrics(candles, idx, direction, horizons)
        matches.append(HistoricalMatch(context=ctx, forward=forward))

    n = len(matches)
    quality = classify_sample(n)
    if n == 0:
        return MatchStats(
            sample_size=0,
            sample_quality=quality,
            status="NO_DATA",
            mean_return_pct=None,
            median_return_pct=None,
            favorable_rate=None,
            mean_mfe_pct=None,
            mean_mae_pct=None,
            horizon=primary_horizon,
            matches=[],
        )

    primary_rets: list[float] = []
    mfes: list[float] = []
    maes: list[float] = []
    for m in matches:
        for fp in m.forward:
            if fp.horizon != primary_horizon:
                continue
            if fp.return_pct is not None:
                primary_rets.append(fp.return_pct)
            if fp.mfe_pct is not None:
                mfes.append(fp.mfe_pct)
            if fp.mae_pct is not None:
                maes.append(fp.mae_pct)

    if quality in (SampleQuality.NO_DATA, SampleQuality.INSUFFICIENT_DATA):
        status = "INSUFFICIENT_EVIDENCE"
    else:
        status = "VALID"

    favorable = (
        sum(1 for r in primary_rets if r > 0) / len(primary_rets) if primary_rets else None
    )

    return MatchStats(
        sample_size=n,
        sample_quality=quality,
        status=status,
        mean_return_pct=statistics.fmean(primary_rets) if primary_rets else None,
        median_return_pct=statistics.median(primary_rets) if primary_rets else None,
        favorable_rate=favorable,
        mean_mfe_pct=statistics.fmean(mfes) if mfes else None,
        mean_mae_pct=statistics.fmean(maes) if maes else None,
        horizon=primary_horizon,
        matches=matches,
    )


def match_stats_dict(stats: MatchStats) -> dict[str, Any]:
    return {
        "sample_size": stats.sample_size,
        "sample_quality": stats.sample_quality.value,
        "status": stats.status,
        "horizon": stats.horizon,
        "mean_return_pct": stats.mean_return_pct,
        "median_return_pct": stats.median_return_pct,
        "favorable_rate": stats.favorable_rate,
        "mean_mfe_pct": stats.mean_mfe_pct,
        "mean_mae_pct": stats.mean_mae_pct,
    }
