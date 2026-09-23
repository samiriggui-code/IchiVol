"""Golden ruleset_backtest parity — T3 must not change builtin trade results.

Fixture generated on ``main`` (pre-T3) via run_ruleset_backtest_on_candles
for every built-in ruleset on seeds 7 and 42 (300 bars).
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.strategy_lab.catalog import list_builtin_rulesets
from app.strategy_lab.ruleset_backtest import run_ruleset_backtest_on_candles
from tests.indicators.test_ichimoku_lookahead import _make_candles

_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "ruleset_backtest_golden.json"


def _trade_snapshot(detail) -> dict:
    t = detail.trade
    return {
        "signal_index": detail.signal_index,
        "entry_index": detail.entry_index,
        "exit_index": detail.exit_index,
        "exit_reason": detail.exit_reason,
        "entry_price": t.entry_price,
        "exit_price": t.exit_price,
        "direction": t.direction.value if hasattr(t.direction, "value") else t.direction,
        "stop_price": detail.stop_price,
        "target_price": detail.target_price,
    }


@pytest.mark.parametrize("seed", [7, 42])
def test_builtin_ruleset_backtest_matches_pre_t3_golden(seed: int):
    golden = json.loads(_FIXTURE.read_text(encoding="utf-8"))
    expected_by_id = golden[f"seed_{seed}"]
    candles = _make_candles(300, seed=seed)

    builtins = list_builtin_rulesets()
    assert {r.id for r in builtins} == set(expected_by_id.keys())

    for rs in builtins:
        result = run_ruleset_backtest_on_candles(
            candles,
            rs,
            symbol="GOLDEN",
            timeframe="1h",
            commission_bps=0,
            slippage_bps=0,
        )
        actual = {
            "n_signals": result.n_signals,
            "n_skipped_in_position": result.n_skipped_in_position,
            "trades": [_trade_snapshot(d) for d in result.details],
        }
        assert actual == expected_by_id[rs.id], f"divergence on {rs.id} seed={seed}"
