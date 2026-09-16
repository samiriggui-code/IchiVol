"""Ground truth carried by a Synthetic Market Lab scenario (mission brief
§14): the label the generator attached when it fabricated the candles.
IchiVol's pipeline never receives this -- only app/synthetic/validation.py
reads it, after the fact, to score what the pipeline actually decided.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class GroundTruth:
    scenario: str
    expected_context: str
    # Inclusive bar-index window (into the scenario's candle list) where the
    # scenario's characteristic behavior should be visible -- e.g. "well
    # into the trend" or "right after the fake breakout", not the warm-up
    # bars where indicators are still PENDING.
    eval_window: tuple[int, int]
    acceptable_decisions: tuple[str, ...]
    forbidden_decisions: tuple[str, ...]
    notes: str = ""
