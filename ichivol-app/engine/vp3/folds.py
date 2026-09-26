"""Walk-forward folds (§5) + purge gate."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

from vp2 import BAR_SECONDS, TIME_STOP_BARS


@dataclass(frozen=True)
class Fold:
    id: str
    train_start: date
    train_end: date  # inclusive
    test_start: date
    test_end: date  # inclusive


WF_FOLDS: tuple[Fold, ...] = (
    Fold("WF1", date(2020, 9, 1), date(2021, 6, 30), date(2021, 7, 1), date(2021, 12, 31)),
    Fold("WF2", date(2020, 9, 1), date(2021, 12, 31), date(2022, 1, 1), date(2022, 6, 30)),
    Fold("WF3", date(2020, 9, 1), date(2022, 6, 30), date(2022, 7, 1), date(2022, 12, 31)),
    Fold("WF4", date(2020, 9, 1), date(2022, 12, 31), date(2023, 1, 1), date(2023, 6, 30)),
    Fold("WF5", date(2020, 9, 1), date(2023, 6, 30), date(2023, 7, 1), date(2023, 12, 31)),
    Fold("WF6", date(2020, 9, 1), date(2023, 12, 31), date(2024, 1, 1), date(2024, 6, 30)),
    Fold("WF7", date(2020, 9, 1), date(2024, 6, 30), date(2024, 7, 1), date(2024, 12, 31)),
)

VALIDATION = Fold("VAL2025", date(2020, 9, 1), date(2024, 12, 31), date(2025, 1, 1), date(2025, 12, 31))
HOLDOUT = Fold("HOLD2026", date(2020, 9, 1), date(2025, 12, 31), date(2026, 1, 1), date(2026, 8, 31))


def _day_start_s(d: date) -> int:
    return int(datetime(d.year, d.month, d.day, tzinfo=timezone.utc).timestamp())


def _day_end_excl_s(d: date) -> int:
    """Exclusive end = midnight UTC after inclusive calendar day."""
    nxt = datetime(d.year, d.month, d.day, tzinfo=timezone.utc) + timedelta(days=1)
    return int(nxt.timestamp())


def fold_test_window_s(fold: Fold) -> tuple[int, int]:
    """[start, end) unix seconds for the fold's test calendar range."""
    return _day_start_s(fold.test_start), _day_end_excl_s(fold.test_end)


def purge_seconds(interval: str) -> int:
    """§5.1.2 — one time-stop horizon between train and scored entries."""
    return TIME_STOP_BARS[interval] * BAR_SECONDS[interval]


def entry_gate_s(fold: Fold, interval: str) -> int:
    """First second at which new entries may open in this fold's test."""
    test0, _ = fold_test_window_s(fold)
    return test0 + purge_seconds(interval)
