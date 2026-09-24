"""Candle quality checks. Detect and report; never repair silently.

``validate_candles`` returns a report listing every issue found. It does not
mutate, drop, interpolate or fill anything: the caller decides (exclude the
series, mark the instrument degraded, ...). Gaps are reported, not judged --
weekends/holidays are legitimate for FX, equities and indices, so the caller
supplies ``max_gap_bars`` (or a calendar-aware policy later).
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Sequence

from app.indicators.ichimoku import Candle


@dataclass(frozen=True)
class QualityIssue:
    code: str
    index: int | None
    detail: str


@dataclass
class QualityReport:
    issues: list[QualityIssue] = field(default_factory=list)
    n_candles: int = 0

    @property
    def ok(self) -> bool:
        return not self.issues

    def codes(self) -> set[str]:
        return {i.code for i in self.issues}

    def code_counts(self) -> dict[str, int]:
        """Per-code issue counts (T12a manifest / Lab responses)."""
        out: dict[str, int] = {}
        for i in self.issues:
            out[i.code] = out.get(i.code, 0) + 1
        return out

    def has(self, code: str) -> bool:
        return code in self.codes()

    def to_dict(self) -> dict:
        return {
            "ok": self.ok,
            "n_candles": self.n_candles,
            "codes": sorted(self.codes()),
            "code_counts": self.code_counts(),
            "n_issues": len(self.issues),
            "degraded": not self.ok,
        }


def validate_candles(
    candles: Sequence[Candle],
    tf_seconds: int,
    *,
    now: int | None = None,
    max_gap_bars: float = 1.5,
    outlier_log_return: float = 0.25,
    stale_after_bars: float = 3.0,
) -> QualityReport:
    """Check ordering, duplicates, OHLC coherence, gaps, outliers, freshness.

    ``now`` (unix seconds) enables the stale / incomplete-last-bar checks;
    without it those two are skipped rather than guessed.
    """
    report = QualityReport(n_candles=len(candles))
    add = report.issues.append

    for i, c in enumerate(candles):
        vals = (c.open, c.high, c.low, c.close, c.volume)
        if any(not math.isfinite(v) for v in vals):
            add(QualityIssue("non_finite", i, "NaN/inf in OHLCV"))
            continue
        if min(c.open, c.high, c.low, c.close) <= 0:
            add(QualityIssue("non_positive_price", i, "price <= 0"))
        if c.high < max(c.open, c.close, c.low) or c.low > min(c.open, c.close, c.high):
            add(QualityIssue("ohlc_incoherent", i, f"o={c.open} h={c.high} l={c.low} c={c.close}"))
        if c.volume < 0:
            add(QualityIssue("negative_volume", i, f"volume={c.volume}"))

        if i == 0:
            continue
        prev = candles[i - 1]
        if c.time == prev.time:
            add(QualityIssue("duplicate", i, f"time={c.time}"))
        elif c.time < prev.time:
            add(QualityIssue("out_of_order", i, f"{c.time} < {prev.time}"))
        else:
            if c.time - prev.time > tf_seconds * max_gap_bars:
                missing = round((c.time - prev.time) / tf_seconds) - 1
                add(QualityIssue("gap", i, f"~{missing} bar(s) missing before t={c.time}"))
            if prev.close > 0 and c.close > 0:
                r = abs(math.log(c.close / prev.close))
                if r > outlier_log_return:
                    add(QualityIssue("outlier_return", i, f"|log return|={r:.3f}"))

    if now is not None and candles:
        last = candles[-1]
        if last.time + tf_seconds > now:
            add(QualityIssue("incomplete_last_bar", len(candles) - 1, "last bar not closed yet"))
        elif now - (last.time + tf_seconds) > tf_seconds * stale_after_bars:
            add(QualityIssue("stale", len(candles) - 1, f"last bar closed {now - (last.time + tf_seconds)}s ago"))
    return report


def closed_candles(candles: Sequence[Candle], tf_seconds: int, now: int) -> list[Candle]:
    """Drop the still-forming bar so signals are never computed on it."""
    return [c for c in candles if c.time + tf_seconds <= now]
