"""T4a — backtest → ChartObject overlay parity + API."""

from __future__ import annotations

import math

import pytest
from fastapi.testclient import TestClient

from app.agents.types import Direction
from app.backtest.engine import Trade
from app.chart_objects.from_backtest import (
    backtest_to_chart_objects,
    trade_outcome,
    trade_return_pct_gross,
    trade_return_pct_net,
)
from app.chart_objects.types import ChartObjectSource, ChartObjectType
from app.main import app
from app.strategy_lab.catalog import get_builtin_ruleset
from app.strategy_lab.ruleset_backtest import (
    RulesetTradeDetail,
    run_ruleset_backtest_on_candles,
)
from tests.indicators.test_ichimoku_lookahead import _make_candles

client = TestClient(app)

# Catalog strategies that produce trades on both golden seeds (from ruleset_backtest_golden).
_RULESETS = (
    "IV_EXP_A_KUMO_BO_001",
    "IV_ICHIMOKU_ONLY_LONG_001",
)


@pytest.mark.parametrize("seed", [7, 42])
@pytest.mark.parametrize("ruleset_id", list(_RULESETS))
def test_overlay_trades_match_backtest_parity(seed: int, ruleset_id: str):
    candles = _make_candles(300, seed=seed)
    ruleset = get_builtin_ruleset(ruleset_id)
    result = run_ruleset_backtest_on_candles(
        candles, ruleset, symbol="T4BTC", timeframe="1h"
    )
    objects = backtest_to_chart_objects(result, candles)

    trade_objects = [o for o in objects if o.origin.get("kind") != "rejected"]
    rejected_objects = [o for o in objects if o.origin.get("kind") == "rejected"]
    assert len(trade_objects) == 4 * len(result.details)
    assert len(rejected_objects) == len(result.rejected)
    for trade_id, detail in enumerate(result.details):
        trade_objs = [o for o in trade_objects if o.origin.get("trade_id") == trade_id]
        assert len(trade_objs) == 4
        by_type = {o.type: o for o in trade_objs}
        assert set(by_type) == {
            ChartObjectType.ENTRY,
            ChartObjectType.STOP,
            ChartObjectType.TARGET,
            ChartObjectType.MARKER,
        }
        entry_t = candles[detail.entry_index].time
        exit_t = candles[detail.exit_index].time
        assert by_type[ChartObjectType.ENTRY].points[0].time == entry_t
        assert by_type[ChartObjectType.ENTRY].points[0].price == detail.trade.entry_price
        assert by_type[ChartObjectType.STOP].points[0].time == entry_t
        assert by_type[ChartObjectType.STOP].points[0].price == detail.stop_price
        assert by_type[ChartObjectType.TARGET].points[0].time == entry_t
        assert by_type[ChartObjectType.TARGET].points[0].price == detail.target_price
        assert by_type[ChartObjectType.MARKER].points[0].time == exit_t
        assert by_type[ChartObjectType.MARKER].points[0].price == detail.trade.exit_price
        assert by_type[ChartObjectType.MARKER].label == detail.exit_reason
        assert by_type[ChartObjectType.ENTRY].source == ChartObjectSource.BACKTEST
        # Indices / prices / reason match backtest detail exactly
        assert by_type[ChartObjectType.ENTRY].origin["entry_index"] == detail.entry_index
        assert by_type[ChartObjectType.ENTRY].origin["exit_index"] == detail.exit_index
        assert by_type[ChartObjectType.ENTRY].origin["exit_reason"] == detail.exit_reason
        assert by_type[ChartObjectType.ENTRY].origin["signal_index"] == detail.signal_index
        assert "why_entered" in by_type[ChartObjectType.ENTRY].origin
        assert "why_exited" in by_type[ChartObjectType.ENTRY].origin
        # Net outcome (not gross)
        origin = by_type[ChartObjectType.ENTRY].origin
        assert "return_pct_net" in origin and "return_pct_gross" in origin
        assert "r_multiple_gross" in origin
        assert origin["outcome"] == trade_outcome(origin["return_pct_net"])


@pytest.mark.parametrize("seed", [7, 42])
def test_overlay_times_on_candles_and_causality(seed: int):
    candles = _make_candles(300, seed=seed)
    last = candles[-1].time
    times = {c.time for c in candles}
    ruleset = get_builtin_ruleset("IV_EXP_A_KUMO_BO_001")
    result = run_ruleset_backtest_on_candles(
        candles, ruleset, symbol="T4BTC", timeframe="1h"
    )
    objects = backtest_to_chart_objects(result, candles)
    for o in objects:
        assert o.as_of == last
        for p in o.points:
            assert p.time in times
            assert p.time <= last


def test_api_outcome_loss_filter(monkeypatch):
    candles = _make_candles(300, seed=7)

    def fake_resolve(symbol, timeframe, limit):
        class P:
            id = "test"

        return P(), symbol, candles[:limit]

    monkeypatch.setattr(
        "app.api.backtest_overlay.resolve_and_fetch", fake_resolve
    )
    all_resp = client.post(
        "/api/engine/strategy-lab/backtest-overlay",
        json={
            "symbol": "T4BTC",
            "timeframe": "1h",
            "limit": 300,
            "ruleset_id": "IV_EXP_A_KUMO_BO_001",
            "outcome": "all",
        },
    )
    assert all_resp.status_code == 200, all_resp.text
    all_body = all_resp.json()
    counts = all_body["counts"]
    assert counts["total"] == len(all_body["trades"])
    for t in all_body["trades"]:
        assert "return_pct_net" in t and "return_pct_gross" in t
        assert "r_multiple_gross" in t
        assert "return_pct" not in t
        assert "r_multiple" not in t

    loss_resp = client.post(
        "/api/engine/strategy-lab/backtest-overlay",
        json={
            "symbol": "T4BTC",
            "timeframe": "1h",
            "limit": 300,
            "ruleset_id": "IV_EXP_A_KUMO_BO_001",
            "outcome": "loss",
        },
    )
    assert loss_resp.status_code == 200
    loss_body = loss_resp.json()
    assert loss_body["counts"] == counts  # counts unchanged
    assert all(t["outcome"] == "loss" for t in loss_body["trades"])
    assert all(t["return_pct_net"] < 0 for t in loss_body["trades"])
    for o in loss_body["objects"]:
        assert o["origin"]["outcome"] == "loss"
    # 4 objects per filtered trade
    assert len(loss_body["objects"]) == 4 * len(loss_body["trades"])


def test_api_unknown_ruleset_404(monkeypatch):
    candles = _make_candles(80, seed=1)

    def fake_resolve(symbol, timeframe, limit):
        class P:
            id = "test"

        return P(), symbol, candles[:limit]

    monkeypatch.setattr(
        "app.api.backtest_overlay.resolve_and_fetch", fake_resolve
    )
    resp = client.post(
        "/api/engine/strategy-lab/backtest-overlay",
        json={"symbol": "T4BTC", "ruleset_id": "DOES_NOT_EXIST"},
    )
    assert resp.status_code == 404


def test_api_invalid_dsl_422(monkeypatch):
    candles = _make_candles(80, seed=1)

    def fake_resolve(symbol, timeframe, limit):
        class P:
            id = "test"

        return P(), symbol, candles[:limit]

    monkeypatch.setattr(
        "app.api.backtest_overlay.resolve_and_fetch", fake_resolve
    )
    resp = client.post(
        "/api/engine/strategy-lab/backtest-overlay",
        json={
            "symbol": "T4BTC",
            "ruleset": {
                "id": "BAD",
                "version": "1",
                "direction": "LONG",
                "conditions": {"not_a_real_key": True},
            },
        },
    )
    assert resp.status_code == 422


def test_trade_outcome_helpers():
    assert trade_outcome(0.01) == "win"
    assert trade_outcome(-0.01) == "loss"
    assert trade_outcome(0.0) == "flat"


def test_gross_win_net_loss_outcome():
    """+5 bps price move with 16 bps round-trip cost → gross win, net loss.

    cost_log filled like ruleset_backtest (2 × one_way).
    """
    from app.backtest.engine import round_trip_cost_log

    entry = 100.0
    exit_px = 100.0 * math.exp(0.0005)  # +5 bps log move
    log_return = math.log(exit_px / entry)
    commission_bps, slippage_bps = 5.0, 3.0
    cost_log = round_trip_cost_log(commission_bps, slippage_bps)
    assert cost_log == pytest.approx(0.0016)
    detail = RulesetTradeDetail(
        trade=Trade(
            entry_time=1,
            exit_time=2,
            direction=Direction.LONG,
            entry_price=entry,
            exit_price=exit_px,
            log_return=log_return,
            cost_log=cost_log,
        ),
        exit_reason="target",
        stop_price=99.0,
        target_price=exit_px,
        atr_at_signal=1.0,
        signal_index=0,
        entry_index=1,
        exit_index=2,
    )

    gross = trade_return_pct_gross(detail)
    net = trade_return_pct_net(detail)
    assert gross > 0
    assert net < 0
    assert trade_outcome(gross) == "win"
    assert trade_outcome(net) == "loss"
    assert net == pytest.approx(math.exp(log_return - cost_log) - 1.0)
