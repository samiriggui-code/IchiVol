"""OF-0 — order flow intrabarre : information nouvelle ou redite de l'OHLCV ?

Spec normative : docs/RS-07-OF0-ORDER-FLOW-SPEC.md (VP0-2026-09-28e).
Mesure seulement, « footprint approximé 1 s ». Aucun effet sur le paper,
le pipeline, VP1 ni location.py.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

PROTOCOL_VERSION = "VP0-2026-09-28e"
HYPOTHESIS_ID = "OF-0-BTC-1h"
SYMBOL = "BTCUSDT"

DOWNLOAD_START = date(2021, 6, 1)
DOWNLOAD_END = date(2024, 12, 31)
MEASURE_START_MS = int(datetime(2021, 7, 1, tzinfo=timezone.utc).timestamp() * 1000)
DATA_END_EXCL_MS = int(datetime(2025, 1, 1, tzinfo=timezone.utc).timestamp() * 1000)

HOUR_MS = 3_600_000
SEC_MS = 1_000

# Paramètres figés (RS-07 §1–§4).
MIN_SECONDS = 3_400
ATR_PERIOD = 14
BUCKETS_PER_ATR = 20
EXTREME_FRAC = 0.2
BURST_SECONDS = 36
RVOL_WINDOW = 20
TARGET_H = 4  # y = ln(open[t+5] / open[t+1])

# Q1 / Q2 (RS-07 §5–§6).
R2_NEW = 0.5
R2_REDUNDANT = 0.8
Q1_MIN_NEW = 2
IC_MIN = 0.02
MIN_PERIODS_SAME_SIGN = 3
BOOT_N = 10_000
SEED = 7
ALPHA = 0.05

# C1 / C2 (RS-07 §9).
C1_REL_TOL = 1e-6
C2_MAX_SHARE = 0.10

FEATURES: tuple[str, ...] = ("F1_poc_loc", "F2_delta_top", "F3_delta_bot", "F4_delta_path", "F5_burst_share")
PERIODS: tuple[tuple[str, int, int], ...] = (
    ("2021S2", int(datetime(2021, 7, 1, tzinfo=timezone.utc).timestamp() * 1000), int(datetime(2022, 1, 1, tzinfo=timezone.utc).timestamp() * 1000)),
    ("2022", int(datetime(2022, 1, 1, tzinfo=timezone.utc).timestamp() * 1000), int(datetime(2023, 1, 1, tzinfo=timezone.utc).timestamp() * 1000)),
    ("2023", int(datetime(2023, 1, 1, tzinfo=timezone.utc).timestamp() * 1000), int(datetime(2024, 1, 1, tzinfo=timezone.utc).timestamp() * 1000)),
    ("2024", int(datetime(2024, 1, 1, tzinfo=timezone.utc).timestamp() * 1000), DATA_END_EXCL_MS),
)
