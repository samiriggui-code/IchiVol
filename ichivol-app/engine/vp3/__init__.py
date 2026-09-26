"""VP3 — B0–B7 entry baselines on the VP2 common harness.

Protocol: docs/VALIDATION-PROTOCOL.md §2 + carte VP3 (A, B, H, J).
Exit = VP2 common (§6) except B0 (hold until window end).
"""

from __future__ import annotations

PROTOCOL_ID = "VP3"
PROTOCOL_VERSION = "VP0-2026-09-26"

# Warm-up: senkou_b=52 + displacement=26 (§5.1.3)
WARMUP_BARS = 52 + 26

STRATEGIES: tuple[str, ...] = ("B0", "B1", "B2", "B5", "B6", "B7")

RVOL_WINDOW = 20
RVOL_MIN = 1.5

HTF_MAP: dict[str, str] = {"1h": "4h", "4h": "1d"}

__all__ = [
    "HTF_MAP",
    "PROTOCOL_ID",
    "PROTOCOL_VERSION",
    "RVOL_MIN",
    "RVOL_WINDOW",
    "STRATEGIES",
    "WARMUP_BARS",
]
