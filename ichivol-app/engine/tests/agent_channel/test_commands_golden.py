"""Golden parity — agent_channel calculate_ichimoku / calculate_rvol."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.agent_channel import commands as cmds
from tests.indicators.test_ichimoku_lookahead import _make_candles

_ICHI = Path(__file__).resolve().parent / "fixtures" / "calculate_ichimoku_golden.json"
_RVOL = Path(__file__).resolve().parent / "fixtures" / "calculate_rvol_golden.json"


@pytest.mark.parametrize("seed", [7, 42])
def test_calculate_ichimoku_matches_golden(seed: int, monkeypatch):
    candles = _make_candles(300, seed=seed)

    class _P:
        id = "binance"

    monkeypatch.setattr(
        cmds,
        "resolve_and_fetch",
        lambda s, tf, lim: (_P(), s, list(candles)),
    )
    actual = cmds.cmd_calculate_ichimoku(
        {"symbol": "BTCUSDT", "timeframe": "1h", "limit": 300}
    )
    golden = json.loads(_ICHI.read_text(encoding="utf-8"))[f"seed_{seed}"]
    assert actual == golden


@pytest.mark.parametrize("seed", [7, 42])
def test_calculate_rvol_matches_golden(seed: int, monkeypatch):
    candles = _make_candles(300, seed=seed)

    class _P:
        id = "binance"

    monkeypatch.setattr(
        cmds,
        "resolve_and_fetch",
        lambda s, tf, lim: (_P(), s, list(candles)),
    )
    actual = cmds.cmd_calculate_rvol(
        {"symbol": "BTCUSDT", "timeframe": "1h", "limit": 300}
    )
    golden = json.loads(_RVOL.read_text(encoding="utf-8"))[f"seed_{seed}"]
    assert actual == golden
