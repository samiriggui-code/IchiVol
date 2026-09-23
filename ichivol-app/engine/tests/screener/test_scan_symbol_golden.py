"""Golden parity — screener scan_symbol via REGISTRY."""

from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from enum import Enum
from pathlib import Path

import pytest

from app.api.serializers import pipeline_dict
from app.config import settings
from app.indicators.registry import serialize_state
from app.market_data import binance_futures
from app.screener import service
from tests.indicators.test_ichimoku_lookahead import _make_candles

_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "scan_symbol_golden.json"


def _serialize(obj):
    if is_dataclass(obj) and not isinstance(obj, type):
        return {k: _serialize(v) for k, v in asdict(obj).items()}
    if isinstance(obj, Enum):
        return obj.value
    if isinstance(obj, list):
        return [_serialize(x) for x in obj]
    if isinstance(obj, dict):
        return {k: _serialize(v) for k, v in obj.items()}
    return obj


def _agent_payload(out) -> dict:
    return {
        "agent": out.agent,
        "direction": out.direction.value,
        "probability": out.probability,
        "confidence": out.confidence,
        "expected_value": out.expected_value,
        "reasons": list(out.reasons),
        "invalidation": list(out.invalidation),
        "metadata": dict(out.metadata),
    }


@pytest.fixture
def _deterministic_scan(monkeypatch):
    monkeypatch.setattr(settings, "decide_on_closed_candles", False)
    monkeypatch.setattr(binance_futures, "fetch_open_interest_hist", lambda *a, **k: [])
    monkeypatch.setattr(binance_futures, "fetch_funding_rate_hist", lambda *a, **k: [])


@pytest.mark.parametrize("seed", [7, 42])
def test_scan_symbol_matches_golden(seed: int, monkeypatch, _deterministic_scan):
    candles = _make_candles(300, seed=seed)

    class _P:
        id = "binance"

    def fake_resolve(symbol, timeframe, limit=300, default_provider="binance"):
        return _P(), symbol, list(candles)

    monkeypatch.setattr("app.screener.service.resolve_and_fetch", fake_resolve)

    row = service.scan_symbol("BTCUSDT", timeframe="1h", limit=300)
    actual = {
        "symbol": row.symbol,
        "exchange": row.exchange,
        "timeframe": row.timeframe,
        "price": row.price,
        "decision": _serialize(row.decision),
        "pipeline": pipeline_dict(row),
        "atr": serialize_state(row.atr) if row.atr else None,
        "ichimoku": _agent_payload(row.ichimoku),
        "rvol": _agent_payload(row.rvol),
        "context": row.context.to_dict() if row.context else None,
        "evidence": _serialize(row.evidence) if row.evidence else None,
    }
    golden = json.loads(_FIXTURE.read_text(encoding="utf-8"))[f"seed_{seed}"]
    assert actual == golden
