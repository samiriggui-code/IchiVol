"""System One adapter — provider routing, tracing, no fake answers."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch

from app.jev.adapter import evaluate, health
from app.jev.providers import resolve_provider
from app.jev.questions import choice_question, noul_question, score_question


def _response(status: int, body: Any) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status
    resp.json.return_value = body
    resp.text = "" if not isinstance(body, str) else body
    return resp


def test_resolve_provider_defaults_to_jevos(monkeypatch: Any) -> None:
    monkeypatch.delenv("JEV_PROVIDER", raising=False)
    monkeypatch.setenv("JEV_URL", "http://jevos-v4:8017")
    monkeypatch.setenv("JEV_API_KEY", "local-key")
    cfg = resolve_provider()
    assert cfg.name == "jevos"
    assert cfg.base_url == "http://jevos-v4:8017"
    assert cfg.score_maturity == "early"


def test_resolve_provider_typesafe(monkeypatch: Any) -> None:
    monkeypatch.setenv("JEV_PROVIDER", "typesafe")
    monkeypatch.setenv("TYPESAFE_API_KEY", "ts-key")
    monkeypatch.delenv("JEV_API_KEY", raising=False)
    cfg = resolve_provider()
    assert cfg.name == "typesafe"
    assert cfg.base_url == "https://api.typesafe.ai"
    assert cfg.api_key == "ts-key"
    assert cfg.score_maturity == "full"


def test_evaluate_missing_key(monkeypatch: Any) -> None:
    monkeypatch.setenv("JEV_PROVIDER", "jevos")
    monkeypatch.setenv("JEV_API_KEY", "")
    monkeypatch.delenv("TYPESAFE_API_KEY", raising=False)
    out = evaluate({"x": 1}, {"review": noul_question("ok?")})
    assert out["ok"] is False
    assert out["error"] == "jev_key_missing"
    assert out["answers"] is None


def test_evaluate_noul_success(monkeypatch: Any) -> None:
    monkeypatch.setenv("JEV_PROVIDER", "jevos")
    monkeypatch.setenv("JEV_API_KEY", "k")
    body = {
        "model": "jevos-v4",
        "answers": {"review": {"type": "noul", "noul": 0.91}},
        "usage": {"input_tokens": 40, "output_tokens": 0},
    }
    with patch("app.jev.adapter.httpx.Client") as client_cls:
        client = MagicMock()
        client.__enter__.return_value = client
        client.post.return_value = _response(200, body)
        client_cls.return_value = client
        out = evaluate("state", {"review": noul_question("ok?")})

    assert out["ok"] is True
    assert out["provider"] == "jevos"
    assert out["response_model"] == "jevos-v4"
    assert out["answers"]["review"]["noul"] == 0.91
    assert out["cost_usd"] == 0.0
    assert out["error"] is None


def test_evaluate_choice_and_score(monkeypatch: Any) -> None:
    monkeypatch.setenv("JEV_PROVIDER", "typesafe")
    monkeypatch.setenv("TYPESAFE_API_KEY", "ts")
    questions = {
        "action": choice_question("act", {"LONG": "l", "HOLD": "h", "ABSTAIN": "a"}),
        "coherence": score_question("rate", ["weak", "mixed", "strong"]),
    }
    body = {
        "model": "jev-1.13.0",
        "answers": {
            "action": {"type": "choice", "choice": "ABSTAIN", "confidence": 0.6},
            "coherence": {"type": "score", "score": 1},
        },
        "usage": {"input_tokens": 1_000_000, "output_tokens": 0},
    }
    with patch("app.jev.adapter.httpx.Client") as client_cls:
        client = MagicMock()
        client.__enter__.return_value = client
        client.post.return_value = _response(200, body)
        client_cls.return_value = client
        out = evaluate({"symbol": "BTCUSDT"}, questions)

    assert out["ok"] is True
    assert out["provider"] == "typesafe"
    assert out["answers"]["action"]["choice"] == "ABSTAIN"
    assert out["answers"]["coherence"]["score"] == 1.0
    assert out["cost_usd"] == 0.042


def test_evaluate_invalid_answer_not_invented(monkeypatch: Any) -> None:
    monkeypatch.setenv("JEV_PROVIDER", "jevos")
    monkeypatch.setenv("JEV_API_KEY", "k")
    body = {"model": "jevos-v4", "answers": {"review": {"noul": "nope"}}}
    with patch("app.jev.adapter.httpx.Client") as client_cls:
        client = MagicMock()
        client.__enter__.return_value = client
        client.post.return_value = _response(200, body)
        client_cls.return_value = client
        out = evaluate("s", {"review": noul_question("ok?")})

    assert out["ok"] is False
    assert out["answers"] is None
    assert out["error"] == "answer_invalid_noul:review"


def test_legacy_client_shape(monkeypatch: Any) -> None:
    from app.jev.client import evaluate as legacy_evaluate

    monkeypatch.setenv("JEV_PROVIDER", "jevos")
    monkeypatch.setenv("JEV_API_KEY", "k")
    body = {
        "model": "jevos-v4",
        "answers": {"review": {"type": "noul", "noul": 0.5}},
    }
    with patch("app.jev.adapter.httpx.Client") as client_cls:
        client = MagicMock()
        client.__enter__.return_value = client
        client.post.return_value = _response(200, body)
        client_cls.return_value = client
        out = legacy_evaluate("s", {"review": noul_question("ok?")})

    assert out["ok"] is True
    assert out["result"]["answers"]["review"]["noul"] == 0.5


def test_health_jevos_ok(monkeypatch: Any) -> None:
    monkeypatch.setenv("JEV_PROVIDER", "jevos")
    monkeypatch.setenv("JEV_API_KEY", "k")
    with patch("app.jev.adapter.httpx.Client") as client_cls:
        client = MagicMock()
        client.__enter__.return_value = client
        client.get.return_value = _response(200, {"status": "ok"})
        client_cls.return_value = client
        out = health()
    assert out["ok"] is True
    assert out["provider"] == "jevos"
    assert out["probe"] == "health"
