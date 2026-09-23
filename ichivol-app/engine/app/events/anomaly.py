"""Causal EventAnomalyDetector — OHLCV (+ optional RVOL/ATR) only.

Anti-lookahead contract (same spirit as REGISTRY / stock-anomaly-detector):
every score at index i uses only candles[0..i], with rolling stats fit on
``shift(1)`` windows (past bars only).

Does NOT import decision/pipeline, news, or calendar.
"""

from __future__ import annotations

import math
from typing import Sequence

from app.events.thresholds import AnomalyThresholds, DEFAULT_THRESHOLDS
from app.events.types import AnomalyType, MarketAnomalyObservation, MarketRegime
from app.indicators.ichimoku import Candle


def _safe_div(num: float, den: float) -> float | None:
    if den is None or not math.isfinite(den) or abs(den) < 1e-12:
        return None
    if not math.isfinite(num):
        return None
    return num / den


def _past_mean_std(values: Sequence[float], end_exclusive: int, window: int) -> tuple[float | None, float | None]:
    """Mean/std of values[max(0,end-window):end] — end is exclusive (past only)."""
    if end_exclusive <= 0 or window <= 0:
        return None, None
    start = max(0, end_exclusive - window)
    chunk = [values[i] for i in range(start, end_exclusive) if math.isfinite(values[i])]
    if len(chunk) < max(5, window // 4):
        return None, None
    mean = sum(chunk) / len(chunk)
    if len(chunk) < 2:
        return mean, None
    var = sum((x - mean) ** 2 for x in chunk) / (len(chunk) - 1)
    std = math.sqrt(var)
    return mean, std if std > 1e-12 else None


def _returns(candles: Sequence[Candle]) -> list[float]:
    out: list[float] = [float("nan")]
    for i in range(1, len(candles)):
        prev = float(candles[i - 1].close)
        cur = float(candles[i].close)
        out.append((cur / prev - 1.0) if prev > 0 else float("nan"))
    return out


def _log_volumes(candles: Sequence[Candle]) -> list[float]:
    out: list[float] = []
    for c in candles:
        v = float(c.volume or 0.0)
        out.append(math.log(v) if v > 0 else float("nan"))
    return out


def detect_anomaly(
    candles: Sequence[Candle],
    *,
    symbol: str,
    timeframe: str,
    rvol: float | None = None,
    atr: float | None = None,
    thresholds: AnomalyThresholds | None = None,
) -> MarketAnomalyObservation:
    """Score the last candle (assumed closed). Pure / causal."""
    thr = thresholds or DEFAULT_THRESHOLDS
    n = len(candles)
    if n < thr.min_history:
        return MarketAnomalyObservation(
            symbol=symbol,
            timeframe=timeframe,
            bar_time=int(candles[-1].time) if n else 0,
            event_suspected=False,
            event_type=AnomalyType.NONE,
            market_regime=MarketRegime.NORMAL_MARKET,
            return_zscore=None,
            volume_zscore=None,
            range_atr_ratio=None,
            gap_atr_ratio=None,
            rvol=rvol,
            volatility_zscore=None,
            confidence=0.0,
            feature_version=thr.feature_version,
            reasons=("insufficient_history",),
        )

    i = n - 1
    c = candles[i]
    prev = candles[i - 1]
    rets = _returns(candles)
    log_vols = _log_volumes(candles)

    # return_z: (r_t - mean(r_{t-w..t-1})) / std(...)
    r_mean, r_std = _past_mean_std(rets, i, thr.z_window)
    ret = rets[i]
    return_z = _safe_div(ret - r_mean, r_std) if r_mean is not None and r_std else None

    # volume_z on log volume, past-only
    v_mean, v_std = _past_mean_std(log_vols, i, thr.vol_z_window)
    volume_z = (
        _safe_div(log_vols[i] - v_mean, v_std) if v_mean is not None and v_std else None
    )

    # volatility_z: |r_t| vs past mean/std of |r|
    abs_rets = [abs(x) if math.isfinite(x) else float("nan") for x in rets]
    a_mean, a_std = _past_mean_std(abs_rets, i, thr.z_window)
    volatility_z = (
        _safe_div(abs_rets[i] - a_mean, a_std) if a_mean is not None and a_std else None
    )

    atr_v = float(atr) if atr is not None and atr > 0 else None
    bar_range = float(c.high) - float(c.low)
    range_atr_ratio = _safe_div(bar_range, atr_v) if atr_v else None
    gap = float(c.open) - float(prev.close)
    gap_atr_ratio = _safe_div(abs(gap), atr_v) if atr_v else None

    reasons: list[str] = []
    price_hit = return_z is not None and abs(return_z) >= thr.return_z_abs
    vol_hit = volume_z is not None and volume_z >= thr.volume_z
    vola_hit = volatility_z is not None and abs(volatility_z) >= thr.volatility_z_abs
    range_hit = range_atr_ratio is not None and range_atr_ratio >= thr.range_atr
    gap_hit = gap_atr_ratio is not None and gap_atr_ratio >= thr.gap_atr
    rvol_hit = rvol is not None and rvol >= thr.rvol

    if price_hit:
        reasons.append(f"|return_z|={abs(return_z):.2f}>={thr.return_z_abs}")
    if vol_hit:
        reasons.append(f"volume_z={volume_z:.2f}>={thr.volume_z}")
    if vola_hit:
        reasons.append(f"|volatility_z|={abs(volatility_z):.2f}>={thr.volatility_z_abs}")
    if range_hit:
        reasons.append(f"range/atr={range_atr_ratio:.2f}>={thr.range_atr}")
    if gap_hit:
        reasons.append(f"|gap|/atr={gap_atr_ratio:.2f}>={thr.gap_atr}")
    if rvol_hit:
        reasons.append(f"rvol={rvol:.2f}>={thr.rvol}")

    price_side = price_hit or range_hit or gap_hit or vola_hit
    volume_side = vol_hit or rvol_hit
    event_suspected = price_side or volume_side

    if price_side and volume_side:
        event_type = AnomalyType.PRICE_VOLUME_SHOCK
    elif gap_hit and not (price_hit or range_hit or vola_hit or volume_side):
        event_type = AnomalyType.GAP_EVENT
    elif vola_hit and not (price_hit or range_hit or volume_side):
        event_type = AnomalyType.VOLATILITY_SHOCK
    elif volume_side and not price_side:
        event_type = AnomalyType.VOLUME_SHOCK
    elif price_side:
        event_type = AnomalyType.PRICE_SHOCK
    else:
        event_type = AnomalyType.NONE

    # Confidence from strongest relative exceedance (capped).
    scores: list[float] = []
    if return_z is not None:
        scores.append(abs(return_z) / thr.return_z_abs)
    if volume_z is not None:
        scores.append(volume_z / thr.volume_z)
    if volatility_z is not None:
        scores.append(abs(volatility_z) / thr.volatility_z_abs)
    if range_atr_ratio is not None:
        scores.append(range_atr_ratio / thr.range_atr)
    if gap_atr_ratio is not None:
        scores.append(gap_atr_ratio / thr.gap_atr)
    if rvol is not None and thr.rvol > 0:
        scores.append(rvol / thr.rvol)
    raw = max(scores) if scores else 0.0
    confidence = 0.0 if not event_suspected else float(min(1.0, max(0.0, (raw - 1.0) / 2.0 + 0.5)))

    # Without news/calendar match yet → UNKNOWN_EVENT if suspected, else NORMAL.
    if event_suspected:
        regime = MarketRegime.UNKNOWN_EVENT
    else:
        regime = MarketRegime.NORMAL_MARKET

    return MarketAnomalyObservation(
        symbol=symbol,
        timeframe=timeframe,
        bar_time=int(c.time),
        event_suspected=event_suspected,
        event_type=event_type,
        market_regime=regime,
        return_zscore=return_z,
        volume_zscore=volume_z,
        range_atr_ratio=range_atr_ratio,
        gap_atr_ratio=gap_atr_ratio,
        rvol=rvol,
        volatility_zscore=volatility_z,
        confidence=confidence,
        feature_version=thr.feature_version,
        reasons=tuple(reasons),
    )


def anomaly_observation_dict(obs: MarketAnomalyObservation | None) -> dict | None:
    if obs is None:
        return None
    return obs.to_dict()
