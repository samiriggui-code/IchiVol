"""VP1 — frozen Univers VP data from data.binance.vision (sha256 manifest).

Protocol: docs/VALIDATION-PROTOCOL.md §4 + carte VP1.
No Twelve Data. No live REST for VP runs once series are frozen.
"""

from __future__ import annotations

from datetime import date

PROTOCOL_ID = "VP1"
PROTOCOL_VERSION = "VP0-2026-09-26"

SYMBOLS: tuple[str, ...] = ("BTCUSDT", "ETHUSDT", "SOLUSDT")
SPOT_INTERVALS: tuple[str, ...] = ("1h", "4h", "1d")

WINDOW_START = date(2020, 9, 1)
WINDOW_END = date(2026, 8, 31)  # inclusive calendar day

VISION_BASE = "https://data.binance.vision"

ENTRY_SOURCE_NOTE = (
    "OI from Vision daily metrics (sum_open_interest); funding from monthly fundingRate. "
    "ETH/SOL metrics may start later than 2020-09-01 → document skip for B4/E/G if incomplete."
)
