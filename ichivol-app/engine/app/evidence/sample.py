"""Sample-size quality labels — never present a win-rate without N."""

from __future__ import annotations

from enum import Enum


class SampleQuality(str, Enum):
    NO_DATA = "NO_DATA"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"
    LOW_SAMPLE = "LOW_SAMPLE"
    VALID_SAMPLE = "VALID_SAMPLE"


# Explicit thresholds (documented, reproducible — not "feels enough").
INSUFFICIENT_MAX = 9
LOW_SAMPLE_MAX = 29


def classify_sample(n: int) -> SampleQuality:
    if n <= 0:
        return SampleQuality.NO_DATA
    if n <= INSUFFICIENT_MAX:
        return SampleQuality.INSUFFICIENT_DATA
    if n <= LOW_SAMPLE_MAX:
        return SampleQuality.LOW_SAMPLE
    return SampleQuality.VALID_SAMPLE
