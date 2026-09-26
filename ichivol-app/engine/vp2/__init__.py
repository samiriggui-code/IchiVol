"""VP2 — common execution harness (§6–§7) on research_lab/sim.py (S1).

Protocol: docs/VALIDATION-PROTOCOL.md §1ter, §6, §7 + carte VP2.
Uses frozen VP1 series only. Strategies B0–B8 arrive in VP3.
"""

from __future__ import annotations

PROTOCOL_ID = "VP2"
PROTOCOL_VERSION = "VP0-2026-09-26"

# Univers VP capital (§1bis / §6)
INITIAL_CAPITAL = 10_000.0
# Frozen RNG seed for multi-symbol shuffle (§1ter)
DEFAULT_SEED = 7

BAR_SECONDS: dict[str, int] = {"1h": 3600, "4h": 14400, "1d": 86400}
TIME_STOP_BARS: dict[str, int] = {"1h": 48, "4h": 24}

__all__ = [
    "BAR_SECONDS",
    "DEFAULT_SEED",
    "INITIAL_CAPITAL",
    "PROTOCOL_ID",
    "PROTOCOL_VERSION",
    "TIME_STOP_BARS",
]
