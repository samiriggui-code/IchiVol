"""Shared timeframe metadata, used by both the live screener
(app/screener/service.py) and the backtest experiments
(app/backtest/experiments.py) for MTF (multi-timeframe) alignment -- one
table, not two copies that could drift apart.
"""

from __future__ import annotations

# No entry for "1d": there's no higher timeframe already wired anywhere in
# the app (the TS client's own INTERVALS list stops at 1d too), so MTF is
# simply skipped for daily scans rather than inventing a weekly timeframe
# nothing else uses.
HIGHER_TIMEFRAME: dict[str, str] = {"15m": "1h", "1h": "4h", "4h": "1d"}

TF_SECONDS: dict[str, int] = {"15m": 900, "1h": 3600, "4h": 14400, "1d": 86400}
