"""AG0 follow-up: outcome stats must ignore pre-AG0 biased entries."""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.api.activity import (
    ENTRY_SOURCE_FIRST_CLOSED_OPEN,
    get_evidence_outcomes,
    include_in_outcome_stats,
)


def test_include_in_outcome_stats_requires_first_closed_open():
    assert include_in_outcome_stats({"entry_source": ENTRY_SOURCE_FIRST_CLOSED_OPEN}) is True
    assert include_in_outcome_stats({"entry_source": "first_closed_open", "price": 111}) is True
    # Pre-AG0 / biased: live price only, or missing marker
    assert include_in_outcome_stats(None) is False
    assert include_in_outcome_stats({}) is False
    assert include_in_outcome_stats({"price": 999.0, "direction": "LONG"}) is False
    assert include_in_outcome_stats({"entry_source": "live_price"}) is False


def _rec(*, entry_source: str | None, ret: float = 0.02, stale: bool = False):
    snapshot: dict = {"direction": "LONG", "first_of_run": True}
    if entry_source is not None:
        snapshot["entry_source"] = entry_source
        snapshot["price"] = 100.0
    else:
        snapshot["price"] = 999.0  # biased live price
    return SimpleNamespace(
        decision="BUY",
        asset_class="crypto",
        context_json={"confluence": {"stage_statuses": {"participation": "pass"}}},
        market_snapshot=snapshot,
        outcome_json={
            "stale": stale,
            "forward_returns": {"5": ret, "10": ret, "20": ret},
            "mfe_pct": 0.03,
            "mae_pct": -0.01,
        },
        outcome_recorded_at=datetime.now(timezone.utc),
    )


def test_get_evidence_outcomes_excludes_rows_without_ag0_entry_source(monkeypatch):
    biased = _rec(entry_source=None, ret=0.50)  # would dominate if included
    ok = _rec(entry_source=ENTRY_SOURCE_FIRST_CLOSED_OPEN, ret=0.02)
    stale_ok = _rec(entry_source=ENTRY_SOURCE_FIRST_CLOSED_OPEN, ret=0.99, stale=True)

    session = MagicMock()
    session.execute.return_value.scalars.return_value = [biased, ok, stale_ok]
    monkeypatch.setattr("app.api.activity.SessionLocal", lambda: session)

    out = get_evidence_outcomes(first_of_run_only=True)
    # Only the AG0-marked non-stale row feeds summarize_outcomes
    assert out["n_used"] == 1
    h = out["groups"][0]["horizons"]["5"]
    assert h["mean_return"] == pytest.approx(0.02)
    session.close.assert_called_once()
