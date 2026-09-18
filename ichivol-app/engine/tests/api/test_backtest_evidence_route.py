"""GET /backtest/evidence -- thin route over app/backtest/evidence.py's
compute_evidence_summary. The scoring logic itself is unit-tested in
tests/backtest/test_evidence.py; this just proves the route wires it up and
that FastAPI resolves `/backtest/evidence` before `/backtest/{symbol}`
(the whole reason this route must be declared first in routes.py).
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_backtest_evidence_route_is_not_shadowed_by_backtest_symbol():
    resp = client.get("/api/engine/backtest/evidence")
    assert resp.status_code == 200
    body = resp.json()
    for key in (
        "enabled", "interval_s", "total_rows", "last_run_at", "first_run_at",
        "distinct_days", "latest_pairs", "pipeline_beats_ichimoku_sharpe", "note",
    ):
        assert key in body


def test_backtest_evidence_route_reports_enabled_flag_from_settings():
    from app.config import settings

    resp = client.get("/api/engine/backtest/evidence")
    assert resp.json()["enabled"] == settings.enable_backtest_evidence
