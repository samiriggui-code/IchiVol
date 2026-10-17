"""Strategic actions Eve may propose (V1: potential only — never auto-executed)."""

from __future__ import annotations

from typing import Literal

EveAction = Literal["LONG", "SHORT", "HOLD", "CLOSE", "ABSTAIN"]

VALID_ACTIONS: frozenset[str] = frozenset({"LONG", "SHORT", "HOLD", "CLOSE", "ABSTAIN"})


def normalize_action(value: str | None) -> EveAction | None:
    if not value:
        return None
    v = value.strip().upper()
    if v in VALID_ACTIONS:
        return v  # type: ignore[return-value]
    # Map baseline combiner vocabulary when useful for comparison.
    if v in ("BUY", "STRONG_BUY"):
        return "LONG"
    if v in ("SELL", "STRONG_SELL"):
        return "SHORT"
    if v in ("WATCH", "NO_TRADE", "NONE"):
        return "ABSTAIN"
    return None
