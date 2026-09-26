"""VP2 harness — frozen §6 exits, full-cash sizing, base/adverse metadata."""

from __future__ import annotations

from app.agents.types import Direction
from app.indicators.ichimoku import Candle
from research_lab.signals import BarSignal
from research_lab.sim import ADVERSE_COST, BASE_COST, CostModel, Rules, simulate
from vp2 import DEFAULT_SEED, INITIAL_CAPITAL, PROTOCOL_VERSION, TIME_STOP_BARS
from vp2.rules import common_rules
from vp2.run import run_from_feed

H = 3600
T0 = 1_700_000_000 - 1_700_000_000 % H
NOFEE = CostModel("nofee", 0.0, 0.0, 0.0)


def sig(t, decision="WATCH", direction=Direction.NEUTRAL, sd=None):
    return BarSignal(
        t,
        decision,
        direction,
        sd,
        1.0,
        (),
        (),
        "signal" if decision in ("BUY", "SELL") else "x",
        None,
    )


def bar(i, o, h, l, c, v=1e9):
    return Candle(time=T0 + i * H, open=o, high=h, low=l, close=c, volume=v)


def series(rows):
    out = {}
    for i, (o, h, l, c, d, sd) in enumerate(rows):
        direction = Direction.LONG if d == "BUY" else Direction.SHORT if d == "SELL" else Direction.NEUTRAL
        out[T0 + i * H] = (bar(i, o, h, l, c), sig(T0 + i * H, d, direction, sd))
    return out


def flat(n, px=100.0, decision="WATCH", sd=None):
    return [(px, px, px, px, decision, sd)] * n


def test_common_rules_freeze_1h_and_4h():
    r1 = common_rules("1h")
    assert r1.exit_mode == "levels_only"
    assert r1.allow_short is False
    assert r1.immediate_fill is False
    assert r1.full_cash is True
    assert r1.max_open == 1
    assert r1.take_profit_r == 2.0
    assert r1.time_stop_bars == TIME_STOP_BARS["1h"] == 48
    assert r1.daily_loss_limit_pct == 0.0
    r4 = common_rules("4h")
    assert r4.time_stop_bars == 24
    assert r4.bar_seconds == 14400


def test_levels_only_ignores_pipeline_flip():
    rows = [(100, 100, 100, 100, "BUY", 2.0), (100, 100, 100, 100, "BUY", 2.0)] + flat(10, 100, "WATCH", 2.0)
    rules = Rules(
        "t",
        exit_mode="levels_only",
        time_stop_bars=48,
        full_cash=True,
        max_open=1,
        max_notional_pct=1.0,
        daily_loss_limit_pct=0.0,
        max_open_risk_pct=10.0,
        allow_short=False,
        liquidity_cap_pct=1.0,
        force_flat_at_end=False,
    )
    res = simulate({"X": series(rows)}, rules, NOFEE, (T0, T0 + 50 * H), initial=10_000.0)
    assert len(res.trades) == 0
    assert len(res.open_at_end) == 1


def test_time_stop_exits_at_close_after_n_bars():
    n = 3
    rows = [(100, 100, 100, 100, "BUY", 5.0), (100, 100, 100, 100, "BUY", 5.0)] + [
        (100, 101, 99, 100.5, "WATCH", 5.0)
    ] * (n + 2)
    rules = Rules(
        "t",
        exit_mode="levels_only",
        time_stop_bars=n,
        bar_seconds=H,
        full_cash=True,
        max_open=1,
        max_notional_pct=1.0,
        daily_loss_limit_pct=0.0,
        max_open_risk_pct=10.0,
        allow_short=False,
        liquidity_cap_pct=1.0,
        force_flat_at_end=False,
    )
    res = simulate({"X": series(rows)}, rules, NOFEE, (T0, T0 + 50 * H), initial=10_000.0)
    assert len(res.trades) == 1
    t = res.trades[0]
    assert t.exit_reason == "time_stop"
    assert t.entry_time == T0 + H
    assert t.exit_time == T0 + H + n * H
    assert t.exit_raw == 100.5


def test_full_cash_sizes_near_initial():
    rows = [(100, 100, 100, 100, "BUY", 2.0), (100, 100, 100, 100, "BUY", 2.0), (100, 100, 96, 97, "WATCH", 2.0)] + flat(
        3, 97
    )
    rules = Rules(
        "t",
        exit_mode="levels_only",
        full_cash=True,
        max_open=1,
        max_notional_pct=1.0,
        daily_loss_limit_pct=0.0,
        max_open_risk_pct=10.0,
        allow_short=False,
        liquidity_cap_pct=1.0,
        force_flat_at_end=False,
        time_stop_bars=None,
    )
    res = simulate({"X": series(rows)}, rules, NOFEE, (T0, T0 + 50 * H), initial=INITIAL_CAPITAL)
    t = res.trades[0]
    assert abs(t.notional - INITIAL_CAPITAL) < 1e-6


def test_short_rejected_under_vp_rules():
    rows = [(100, 100, 100, 100, "SELL", 2.0)] + flat(5, 100, "SELL", 2.0)
    run = run_from_feed({"X": series(rows)}, interval="1h", window=(T0, T0 + 50 * H), symbol="X")
    assert run.meta.allow_short is False
    assert run.result.rejections.get("short_not_allowed", 0) >= 1
    assert run.meta.n_trades == 0


def test_run_meta_includes_protocol_seed_cost():
    rows = flat(5)
    rb = run_from_feed({"BTCUSDT": series(rows)}, interval="1h", cost_profile="base", window=(T0, T0 + 50 * H))
    ra = run_from_feed({"BTCUSDT": series(rows)}, interval="1h", cost_profile="adverse", window=(T0, T0 + 50 * H))
    assert rb.meta.protocol_version == PROTOCOL_VERSION
    assert rb.meta.seed == DEFAULT_SEED
    assert rb.meta.cost_profile == "base"
    assert ra.meta.cost_profile == "adverse"
    assert rb.meta.exit_mode == "levels_only"
    assert rb.meta.time_stop_bars == 48
    assert BASE_COST.name == "base" and ADVERSE_COST.name == "adverse"


def test_force_flat_at_end():
    rows = [(100, 100, 100, 100, "BUY", 2.0), (100, 100, 100, 100, "BUY", 2.0)] + flat(5, 100, "WATCH", 2.0)
    rules = Rules(
        "vp2_common",
        risk_pct=1.0,
        take_profit_r=2.0,
        max_open=1,
        max_notional_pct=1.0,
        max_symbol_notional_pct=1.0,
        max_open_risk_pct=10.0,
        daily_loss_limit_pct=0.0,
        allow_short=False,
        liquidity_cap_pct=1.0,
        exit_mode="levels_only",
        immediate_fill=False,
        bar_seconds=H,
        time_stop_bars=10_000,
        full_cash=True,
        force_flat_at_end=True,
    )
    win = (T0, T0 + 6 * H)
    res = simulate({"X": series(rows)}, rules, NOFEE, win, initial=10_000.0)
    assert len(res.trades) == 1
    assert res.trades[0].exit_reason == "window_end"
    assert res.open_at_end == []


def test_deterministic_seed():
    rows = [(100, 100, 100, 100, "BUY", 2.0), (100, 106, 100, 105, "BUY", 2.0)] + flat(4, 105, "WATCH", 2.0)
    a = run_from_feed({"X": series(rows)}, interval="1h", window=(T0, T0 + 50 * H), seed=7)
    b = run_from_feed({"X": series(rows)}, interval="1h", window=(T0, T0 + 50 * H), seed=7)
    assert [t.net for t in a.result.trades] == [t.net for t in b.result.trades]
