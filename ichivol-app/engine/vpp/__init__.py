"""VP-P — faithful simulation + diagnostic of the running paper strategy (ICHIVOL_BASELINE_V1).

Protocol: docs/VALIDATION-PROTOCOL.md, amendement ``VP0-2026-09-27b`` (Question P, pre-registered).
Audit of what the paper really executes: docs/VP-P-PAPER-REEL.md.

Diagnostic only: no EDGE claim, no §9 verdict. Development folds only — the data window stops on
2024-12-31, so the 2025 validation and the 2026 holdout are never downloaded or read.
"""

from __future__ import annotations

from datetime import date

from research_lab.universe import A_UNIVERSE

PROTOCOL_ID = "VP-P"
PROTOCOL_VERSION = "VP0-2026-09-27b"

# The 20 crypto symbols the live auto_watchlist scans (app/universe/catalog.default_watchlist, crypto part).
U20: tuple[str, ...] = tuple(A_UNIVERSE)
# Bridge with VP3 (same symbols as Univers VP), same shared-capital rules.
U3: tuple[str, ...] = ("BTCUSDT", "ETHUSDT", "SOLUSDT")

INTERVALS: tuple[str, ...] = ("1h", "4h")

# Data window: protocol start → end of development. Never beyond 2024-12-31 (validation / holdout untouched).
DATA_START = date(2020, 9, 1)
DATA_END = date(2024, 12, 31)  # inclusive

# Paper initial capital (ICHIVOL_BASELINE_V1.initial_cash_eur) and the frozen VP ordering seed.
INITIAL_CAPITAL = 5000.0
SEED = 7

# Live screener fetches 300 candles and drops the forming one -> 299 closed bars per decision.
LIVE_WINDOW_BARS = 299

# WF test folds (VALIDATION-PROTOCOL §5), inclusive calendar dates.
FOLDS: tuple[tuple[str, str, str], ...] = (
    ("WF1", "2021-07-01", "2021-12-31"),
    ("WF2", "2022-01-01", "2022-06-30"),
    ("WF3", "2022-07-01", "2022-12-31"),
    ("WF4", "2023-01-01", "2023-06-30"),
    ("WF5", "2023-07-01", "2023-12-31"),
    ("WF6", "2024-01-01", "2024-06-30"),
    ("WF7", "2024-07-01", "2024-12-31"),
)

__all__ = [
    "DATA_END",
    "DATA_START",
    "FOLDS",
    "INITIAL_CAPITAL",
    "INTERVALS",
    "LIVE_WINDOW_BARS",
    "PROTOCOL_ID",
    "PROTOCOL_VERSION",
    "SEED",
    "U20",
    "U3",
]
