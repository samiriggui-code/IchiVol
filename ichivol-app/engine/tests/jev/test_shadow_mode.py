"""Ève Shadow mode (JEV) — not ShadowBroker."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

from app.jev.shadow import compare_decision


def test_compare_decision_noul_no_execution(monkeypatch: Any, tmp_path: Any) -> None:
    monkeypatch.setenv("JEV_PROVIDER", "jevos")
    monkeypatch.setenv("JEV_API_KEY", "k")
    monkeypatch.setattr("app.jev.history.DB_PATH", tmp_path / "history.db")

    body = {
        "model": "jevos-v4",
        "answers": {"review": {"type": "noul", "noul": 0.77}},
        "usage": {"input_tokens": 12, "output_tokens": 0},
    }
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = body

    with patch("app.jev.adapter.httpx.Client") as client_cls:
        client = MagicMock()
        client.__enter__.return_value = client
        client.post.return_value = resp
        client_cls.return_value = client
        out = compare_decision(
            {
                "symbol": "BTCUSDT",
                "timeframe": "1h",
                "pipeline": {"decision": "BUY"},
            }
        )

    assert out["mode"] == "shadow"
    assert out["execution_allowed"] is False
    assert out["original_decision"] == "BUY"
    assert out["provider"] == "jevos"
    assert out["response_model"] == "jevos-v4"
    assert out["jev"]["ok"] is True
    assert out["jev"]["result"]["answers"]["review"]["noul"] == 0.77
