"""Overview mark fallback must not block when Twelve Data credits are saturated."""

from __future__ import annotations

import time

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.paper.marks import OVERVIEW_FETCH_BUDGET_S, resolve_marks


client = TestClient(app)


def test_resolve_marks_nonblocking_when_credits_exhausted(monkeypatch):
    import app.market_data.twelve_data as td

    monkeypatch.setattr(td, "_try_acquire_credit_slot", lambda: False)

    def _boom_wait():
        raise TimeoutError("should_not_block")

    monkeypatch.setattr(td, "_wait_for_credit_slot", _boom_wait)

    # Force miss on screener cache
    monkeypatch.setattr(
        "app.paper.marks.peek_screener_marks", lambda: {}
    )

    t0 = time.monotonic()
    out = resolve_marks(
        ["AAPL"],
        timeframe="1h",
        allow_fetch=True,
        fetch_budget_s=OVERVIEW_FETCH_BUDGET_S,
        block_on_provider=False,
    )
    elapsed = time.monotonic() - t0
    assert elapsed < 3.0
    assert out["AAPL"].source == "missing"


def test_overview_responds_under_3s_with_saturated_limiter(monkeypatch):
    import app.market_data.twelve_data as td

    monkeypatch.setattr(td, "_try_acquire_credit_slot", lambda: False)

    def _sleep_forever():
        time.sleep(60)

    monkeypatch.setattr(td, "_wait_for_credit_slot", _sleep_forever)
    monkeypatch.setattr("app.paper.marks.peek_screener_marks", lambda: {})

    t0 = time.monotonic()
    resp = client.get("/api/engine/paper/portfolios/ICHIVOL_BASELINE_V1/overview")
    elapsed = time.monotonic() - t0
    assert elapsed < 3.0, elapsed
    # 200 if baseline exists, else 404 — either way must not hang
    assert resp.status_code in (200, 404)
