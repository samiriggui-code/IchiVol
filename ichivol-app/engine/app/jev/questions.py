"""Builders for System One question payloads (NOUL / CHOICE / SCORE)."""

from __future__ import annotations

from typing import Any


def noul_question(
    instructions: str,
    *,
    criteria: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Yes/no calibrated probability (P(true) in [0, 1])."""
    q: dict[str, Any] = {"type": "noul", "instructions": instructions}
    if criteria is not None:
        q["criteria"] = criteria
    return q


def choice_question(
    instructions: str,
    criteria: dict[str, str | None],
) -> dict[str, Any]:
    """Pick one named option. ``criteria`` maps option id → description (may be null)."""
    if not criteria:
        raise ValueError("choice_criteria_required")
    if len(criteria) > 255:
        raise ValueError("choice_criteria_too_many")
    return {"type": "choice", "instructions": instructions, "criteria": dict(criteria)}


def score_question(
    instructions: str,
    criteria: list[str],
) -> dict[str, Any]:
    """Ordered rubric (2–10 levels). Level index is zero-based in the response."""
    if len(criteria) < 2 or len(criteria) > 10:
        raise ValueError("score_criteria_length")
    return {"type": "score", "instructions": instructions, "criteria": list(criteria)}
