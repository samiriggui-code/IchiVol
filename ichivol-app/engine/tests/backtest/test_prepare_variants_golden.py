"""Golden parity — prepare_variants via REGISTRY."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.backtest import experiments
from app.indicators.registry import serialize_state
from tests.indicators.test_ichimoku_lookahead import _make_candles

_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "prepare_variants_indicators_golden.json"


@pytest.mark.parametrize("seed", [7, 42])
def test_prepare_variants_matches_golden(seed: int, monkeypatch):
    candles = _make_candles(300, seed=seed)

    class _P:
        id = "binance"

    monkeypatch.setattr(experiments, "HIGHER_TIMEFRAME", {})
    monkeypatch.setattr(
        experiments,
        "resolve_and_fetch",
        lambda s, tf, lim, default_provider="binance": (_P(), s, list(candles)),
    )
    prepared = experiments.prepare_variants("BTCUSDT", timeframe="1h", limit=300)
    actual = {
        "symbol": prepared.symbol,
        "timeframe": prepared.timeframe,
        "n_candles": len(prepared.candles),
        "atr_states": [serialize_state(s) for s in prepared.atr_states],
        "positions": {
            k: [d.value for d in series] for k, series in prepared.positions.items()
        },
    }
    golden = json.loads(_FIXTURE.read_text(encoding="utf-8"))[f"seed_{seed}"]
    assert actual == golden
