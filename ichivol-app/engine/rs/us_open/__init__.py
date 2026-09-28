"""RS-U0 — porte descriptive « ouverture US 09:30 New York » (docs/RS-05-US-OPEN-SPEC.md).

Mesure seulement : aucune simulation de portefeuille, aucun changement du paper,
du pipeline ni de VP1. Données 5 min propres à RS-U0.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

PROTOCOL_VERSION = "VP0-2026-09-28c"
HYPOTHESIS_ID = "RS-U0-U3-5m"

SYMBOLS: tuple[str, ...] = ("BTCUSDT", "ETHUSDT", "SOLUSDT")
INTERVAL = "5m"
BAR_MS = 5 * 60 * 1000

# Fenêtre (RS-05 §1). Téléchargement dès juin 2021 : les ancrages du 2021-07-01
# ont besoin des 24 h précédentes (range 6 h + volume de référence 24 h).
DAY_START = date(2021, 7, 1)
DAY_END = date(2024, 12, 31)
DOWNLOAD_START = date(2021, 6, 1)
DATA_END_EXCL_MS = int(datetime(2025, 1, 1, tzinfo=timezone.utc).timestamp() * 1000)

# Paramètres figés (RS-05 §3).
RANGE_BARS = 72  # 6 h
SWEEP_BARS = 3  # 15 min
HORIZON_BARS = 12  # 60 min
VOL_REF_BARS = 288  # 24 h, pour volshare15

# Ancrages : 48 demi-heures, heure locale New York. A* = 09:30.
ANCHOR_MINUTES: tuple[int, ...] = tuple(range(0, 24 * 60, 30))
TARGET_MINUTE = 9 * 60 + 30

# Coûts paper aller-retour, bps (RS-05 §3) : 2 × (7,5 + friction).
PAPER_COMMISSION_BPS = 7.5
PAPER_FRICTION_BPS: dict[str, float] = {"BTCUSDT": 1.0, "ETHUSDT": 1.0, "SOLUSDT": 1.5}


def round_trip_cost_bps(symbol: str) -> float:
    return 2.0 * (PAPER_COMMISSION_BPS + PAPER_FRICTION_BPS[symbol])


# Porte (RS-05 §5).
G1_TOP = 3
G3_MAX_RANK = 5
G4_MIN_EVENTS = 100
MIN_ASSETS = 2

BOOT_N = 10_000
SEED = 7
