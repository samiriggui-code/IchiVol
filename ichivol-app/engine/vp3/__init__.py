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
# VP-S1 Bouclier (amendement VP0-2026-09-27) — N T10b +12 → 48
SHIELD_STRATEGIES: tuple[str, ...] = ("BM", "BN")

RVOL_WINDOW = 20
RVOL_MIN = 1.5

HTF_MAP: dict[str, str] = {"1h": "4h", "4h": "1d"}

# DSR reporté pour M/N (non bloquant) — N après ledger BM/BN
N_T10B_SHIELD = 48

__all__ = [
    "HTF_MAP",
    "N_T10B_SHIELD",
    "PROTOCOL_ID",
    "PROTOCOL_VERSION",
    "RVOL_MIN",
    "RVOL_WINDOW",
    "SHIELD_STRATEGIES",
    "STRATEGIES",
    "WARMUP_BARS",
]
