"""T11a — observation-only data quality gate + series provenance.

Wraps ``validate_candles`` + timing flags into a screener / Lab stamp.
Never mutates pipeline decision, combiner confidence, or paper gates.
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass
from typing import Sequence

from app.indicators.ichimoku import Candle
from app.market_data.quality import QualityReport, validate_candles
from app.screener.timing import SignalTiming

DATA_QUALITY_VERSION = "data_quality_v0"
DATA_PROVENANCE_VERSION = "data_provenance_v0"

_DISCLAIMER_QUALITY = (
    "Data quality observation (T11a) — does not alter decision or confidence."
)
_DISCLAIMER_PROVENANCE = (
    "Data provenance observation (T11a) — audit stamp only; no pipeline vote."
)

# Codes that mark the observation gate as fail (still observation-only).
_FAIL_CODES = frozenset(
    {
        "non_finite",
        "non_positive_price",
        "ohlc_incoherent",
        "negative_volume",
        "duplicate",
        "out_of_order",
    }
)
# Codes that mark watch (soft).
_WATCH_CODES = frozenset(
    {
        "gap",
        "outlier_return",
        "incomplete_last_bar",
        "stale",
    }
)


@dataclass(frozen=True)
class DataQualityObservation:
    version: str
    ok: bool
    gate: str
    """pass | watch | fail — display/research only; never votes BUY/SELL."""
    n_candles: int
    issue_count: int
    issue_codes: tuple[str, ...]
    issues: tuple[dict, ...]
    stale: bool | None
    data_late: bool | None
    lag_bars: int | None
    disclaimer: str = _DISCLAIMER_QUALITY

    def to_dict(self) -> dict:
        return {
            "version": self.version,
            "ok": self.ok,
            "gate": self.gate,
            "n_candles": self.n_candles,
            "issue_count": self.issue_count,
            "issue_codes": list(self.issue_codes),
            "issues": list(self.issues),
            "stale": self.stale,
            "data_late": self.data_late,
            "lag_bars": self.lag_bars,
            "disclaimer": self.disclaimer,
        }


@dataclass(frozen=True)
class DataProvenanceObservation:
    version: str
    provider: str
    symbol: str
    timeframe: str
    n_bars: int
    first_bar_time: int | None
    last_bar_time: int | None
    closed_only: bool
    transforms: tuple[str, ...]
    dataset_fingerprint: str
    disclaimer: str = _DISCLAIMER_PROVENANCE

    def to_dict(self) -> dict:
        return {
            "version": self.version,
            "provider": self.provider,
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "n_bars": self.n_bars,
            "first_bar_time": self.first_bar_time,
            "last_bar_time": self.last_bar_time,
            "closed_only": self.closed_only,
            "transforms": list(self.transforms),
            "dataset_fingerprint": self.dataset_fingerprint,
            "disclaimer": self.disclaimer,
        }


def _gate_from_report(
    report: QualityReport,
    *,
    stale: bool | None,
    data_late: bool | None,
) -> str:
    codes = report.codes()
    if codes & _FAIL_CODES or stale is True:
        return "fail"
    if codes & _WATCH_CODES or data_late is True:
        return "watch"
    if report.ok:
        return "pass"
    return "watch"


def dataset_fingerprint(candles: Sequence[Candle]) -> str:
    """Stable short id for the closed series (times + last close)."""
    if not candles:
        return "empty"
    payload = f"{len(candles)}:{candles[0].time}:{candles[-1].time}:{candles[-1].close:.10g}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def observe_data_quality(
    candles: Sequence[Candle],
    tf_seconds: int,
    *,
    now: int | None = None,
    timing: SignalTiming | None = None,
) -> DataQualityObservation:
    """Run ``validate_candles`` and map to an observation gate."""
    report = validate_candles(candles, tf_seconds, now=now)
    stale = timing.stale if timing is not None else None
    data_late = timing.data_late if timing is not None else None
    lag_bars = timing.lag_bars if timing is not None else None
    # Cap issue payload for API (keep codes complete).
    slim_issues = tuple(
        {"code": i.code, "index": i.index, "detail": i.detail} for i in report.issues[:32]
    )
    codes = tuple(sorted(report.codes()))
    return DataQualityObservation(
        version=DATA_QUALITY_VERSION,
        ok=report.ok and not (stale is True),
        gate=_gate_from_report(report, stale=stale, data_late=data_late),
        n_candles=report.n_candles,
        issue_count=len(report.issues),
        issue_codes=codes,
        issues=slim_issues,
        stale=stale,
        data_late=data_late,
        lag_bars=lag_bars,
    )


def observe_data_provenance(
    candles: Sequence[Candle],
    *,
    provider: str,
    symbol: str,
    timeframe: str,
    closed_only: bool,
    transforms: Sequence[str] = (),
) -> DataProvenanceObservation:
    """Stamp series identity for audit / Lab replay (no decision effect)."""
    return DataProvenanceObservation(
        version=DATA_PROVENANCE_VERSION,
        provider=provider,
        symbol=symbol,
        timeframe=timeframe,
        n_bars=len(candles),
        first_bar_time=candles[0].time if candles else None,
        last_bar_time=candles[-1].time if candles else None,
        closed_only=closed_only,
        transforms=tuple(transforms),
        dataset_fingerprint=dataset_fingerprint(candles),
    )


def data_quality_observation_dict(obs: DataQualityObservation | None) -> dict | None:
    if obs is None:
        return None
    return obs.to_dict()


def data_provenance_observation_dict(
    obs: DataProvenanceObservation | None,
) -> dict | None:
    if obs is None:
        return None
    return obs.to_dict()


def observe_now() -> int:
    return int(time.time())
