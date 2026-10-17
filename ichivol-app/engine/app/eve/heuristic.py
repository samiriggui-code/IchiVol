"""Labelled deterministic fallback when System One is unavailable.

Complements engine-based Analyst/Challenger/Guardian with ``use_jev=False``.
Never invents JEV probabilities. Inspired by buberlo HeuristicJudge +
jarrodwatts MockModel stand-in badge.
"""

from __future__ import annotations

from typing import Any

from app.eve.actions import normalize_action


def heuristic_badge(degradation: dict[str, Any] | None) -> dict[str, Any]:
    """UI / dossier badge — never silent when JEV is degraded."""
    deg = degradation or {}
    level = str(deg.get("level") or "healthy")
    source = str(deg.get("source") or "jev")
    if level == "healthy" and source == "jev":
        return {
            "label": "jev",
            "stand_in": False,
            "level": level,
        }
    return {
        "label": source if source in ("heuristic", "deterministic", "degraded", "offline-demo") else "heuristic",
        "stand_in": True,
        "level": level,
        "reasons": list(deg.get("reasons") or []),
        "note": "System One unavailable or degraded — deterministic engines only",
    }


def heuristic_action_from_baseline(baseline_decision: str | None) -> str:
    """Map baseline BUY/SELL to Eve action when JEV is down (still potential only)."""
    return normalize_action(baseline_decision) or "ABSTAIN"
