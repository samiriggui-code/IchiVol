"""Golden parity — evidence in-window catalog via REGISTRY."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.evidence.catalog import build_in_window_catalog
from tests.indicators.test_ichimoku_lookahead import _make_candles

_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "in_window_catalog_golden.json"


@pytest.mark.parametrize("seed", [7, 42])
def test_in_window_catalog_matches_golden(seed: int):
    golden = json.loads(_FIXTURE.read_text(encoding="utf-8"))[f"seed_{seed}"]
    catalog = build_in_window_catalog(
        _make_candles(300, seed=seed),
        symbol="BTCUSDT",
        timeframe="1h",
        provider="binance",
        asset_class="crypto",
        min_bars=80,
        step=5,
    )
    actual = [{"index": i, "context": ctx.to_dict()} for ctx, _c, i in catalog]
    assert actual == golden
