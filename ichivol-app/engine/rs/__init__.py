"""Chantier RS — stratégies alternatives pré-enregistrées (docs/RS-03-DONCHIAN-4H-SPEC.md).

Module isolé : ne modifie ni le paper, ni le pipeline, ni research_lab/sim.py.
"""

from __future__ import annotations

from datetime import datetime, timezone

PROTOCOL_VERSION = "VP0-2026-09-28b"
HYPOTHESIS_ID = "RS-D1-U3-4h"

SYMBOLS: tuple[str, ...] = ("BTCUSDT", "ETHUSDT", "SOLUSDT")
INTERVAL = "4h"
BAR_SECONDS = 4 * 3600

# Fenêtres (UTC). Données ≥ DATA_END_EXCL jamais lues.
SCORE_START = int(datetime(2021, 7, 1, tzinfo=timezone.utc).timestamp())
DATA_END_EXCL = int(datetime(2025, 1, 1, tzinfo=timezone.utc).timestamp())

# Paramètres figés RS-03 (aucune optimisation).
ENTRY_PERIOD = 55
EXIT_PERIOD = 20
ATR_PERIOD = 14
STOP_ATR_MULT = 3.0

# Taille / limites du paper (RS-03 §5).
INITIAL_CAPITAL = 5000.0
RISK_PCT = 0.005
MAX_NOTIONAL_PCT = 0.10
MAX_OPEN_RISK_PCT = 0.04
DAILY_LOSS_LIMIT_PCT = 0.03
MIN_FILL_FRACTION = 0.25
MIN_NOTIONAL = 10.0
MAX_OPEN = 10
SEED = 7

# Coûts (RS-03 §6), bps par côté.
PAPER_COMMISSION_BPS = 7.5
PAPER_FRICTION_BPS: dict[str, float] = {"BTCUSDT": 1.0, "ETHUSDT": 1.0, "SOLUSDT": 1.5}
ADVERSE_COMMISSION_BPS = 10.0
ADVERSE_SLIPPAGE_BPS = 8.0
ADVERSE_MIN_SPREAD_BPS = 4.0

BOOT_N = 10_000

# Plis WF (VALIDATION-PROTOCOL §5), bornes inclusives en dates UTC.
FOLDS: tuple[tuple[str, str, str], ...] = (
    ("WF1", "2021-07-01", "2021-12-31"),
    ("WF2", "2022-01-01", "2022-06-30"),
    ("WF3", "2022-07-01", "2022-12-31"),
    ("WF4", "2023-01-01", "2023-06-30"),
    ("WF5", "2023-07-01", "2023-12-31"),
    ("WF6", "2024-01-01", "2024-06-30"),
    ("WF7", "2024-07-01", "2024-12-31"),
)

# Validation 2025 (amendement VP0-2026-09-28d) — run unique, règles inchangées. Holdout 2026 fermé.
VAL_SCORE_START = int(datetime(2025, 1, 1, tzinfo=timezone.utc).timestamp())
VAL_DATA_END_EXCL = int(datetime(2026, 1, 1, tzinfo=timezone.utc).timestamp())
VAL_B0E_WEIGHT = 0.05798188750836816  # exposition moyenne RS-D1 en dev (rsd1_results.json), figée
VAL_MIN_TRADES = 10
