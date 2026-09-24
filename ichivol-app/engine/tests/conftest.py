"""Shared pytest fixtures. T13c: clear kill/daily locks between tests.

Shared ICHIVOL_BASELINE_V1 is polluted when a test drops cash (e.g. insufficient
funds) and ``maybe_trip_daily_loss_lock`` latches — later opens then 422 with
``daily_loss_halt`` instead of the expected reason. Locks never auto-clear
in production; tests must start unlocked.
"""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.db.models import PaperPortfolio
from app.db.session import SessionLocal


@pytest.fixture(autouse=True)
def _clear_paper_entry_locks():
    session = SessionLocal()
    try:
        for pf in session.execute(select(PaperPortfolio)).scalars():
            if getattr(pf, "kill_switch_armed", False):
                pf.kill_switch_armed = False
                pf.kill_switch_armed_at = None
            if getattr(pf, "daily_loss_locked", False):
                pf.daily_loss_locked = False
                pf.daily_loss_locked_at = None
        session.commit()
    except Exception:
        session.rollback()
    finally:
        session.close()
    yield
