"""VP-P: paper-faithful simulator options + diagnostic definitions (amendement VP0-2026-09-27b)."""

from app.agents.types import Direction
from app.indicators.ichimoku import Candle
from app.paper.risk import size_position
from app.paper.strategy_profiles import BASELINE_PROFILE
from research_lab.signals import BarSignal
from research_lab.sim import CostModel, Rules, simulate

from vpp import LIVE_WINDOW_BARS
from vpp import diagnose as dg
from vpp.paper import adverse_costs, paper_costs, paper_rules
from vpp.signals import build_feed

H = 3600
T0 = 1_700_000_000 - 1_700_000_000 % H
NOFEE = CostModel("nofee", 0.0, 0.0, 0.0)
WIN = (T0, T0 + 80 * H)


def sig(t, decision="WATCH", direction=Direction.NEUTRAL, sd=None):
    return BarSignal(t, decision, direction, sd, 1.0, (), (), "signal" if decision == "BUY" else "x", None)


def series(rows):
    """rows: (o, h, l, c, decision, direction, sd)."""
    out = {}
    for i, (o, h, l, c, d, dr, sd) in enumerate(rows):
        t = T0 + i * H
        out[t] = (Candle(time=t, open=o, high=h, low=l, close=c, volume=1e6), sig(t, d, dr, sd))
    return out


L, N = Direction.LONG, Direction.NEUTRAL


def flat(n, px=100.0, d=N):
    return [(px, px, px, px, "WATCH", d, None)] * n


def paper(**kw):
    base = paper_rules()
    return Rules(**{**base.__dict__, "daily_loss_limit_pct": 0.0, **kw})


# --- profile mapping ---------------------------------------------------------------------------------------------

def test_rules_come_from_the_live_profile():
    r = paper_rules()
    assert r.risk_pct == BASELINE_PROFILE["risk_pct"] == 0.005
    assert r.max_notional_pct == BASELINE_PROFILE["max_notional_pct"] == 0.10
    assert r.max_open == BASELINE_PROFILE["max_open_positions"] == 10
    assert r.max_open_risk_pct == 0.04 and r.daily_loss_limit_pct == 0.03
    assert r.exit_mode == "direction" and r.time_stop_bars is None and not r.full_cash
    assert r.levels_anchor == "fill" and r.gate_equity == "cost" and r.min_fill_fraction == 0.25
    assert r.max_symbol_notional_pct == 1.0  # key absent from the profile = gate off


def test_costs_friction_replaces_spread_and_slippage():
    c = paper_costs(["BTCUSDT", "PEPEUSDT"])
    assert (c["BTCUSDT"].commission_bps, c["BTCUSDT"].spread_bps, c["BTCUSDT"].slippage_bps) == (7.5, 1.0, 0.0)
    assert c["PEPEUSDT"].spread_bps == 14.6
    a = adverse_costs(["BTCUSDT", "PEPEUSDT"])
    assert (a["BTCUSDT"].commission_bps, a["BTCUSDT"].spread_bps, a["BTCUSDT"].slippage_bps) == (10.0, 4.0, 8.0)
    assert a["PEPEUSDT"].spread_bps == 14.6


# --- simulator options -------------------------------------------------------------------------------------------

def test_sizing_matches_paper_size_position_and_levels_on_fill():
    cost = CostModel("c", 7.5, 1.0, 0.0)
    rows = [(100, 100, 100, 100, "BUY", L, 2.0), (100, 100, 100, 100, "BUY", L, 2.0)] + flat(3, d=L)
    res = simulate({"XUSDT": series(rows)}, paper(), cost, WIN, initial=5000.0)
    ref = size_position(equity=5000.0, cash=5000.0, direction="LONG", entry_price=100.0, stop_distance=2.0,
                        risk_pct=0.005, take_profit_r=2.0, max_notional_pct=0.10, commission_bps=7.5,
                        spread_bps=1.0, slippage_bps=0.0, min_fill_fraction=0.25, min_notional=10.0)
    assert res.open_at_end and abs(res.open_at_end[0]["qty"] - ref.qty) < 1e-9
    # 0.5 % risk would be 12.5 units = 1250 € > 10 % cap -> capped at 500 €
    assert abs(ref.notional - 500.0) < 1e-6


def test_stop_anchored_on_fill_not_on_raw_open():
    cost = CostModel("c", 0.0, 100.0, 0.0)  # 1 % friction makes the difference visible
    rows = [(100, 100, 100, 100, "BUY", L, 2.0), (100, 100, 100, 100, "BUY", L, 2.0),
            (100, 100, 98.5, 99, "WATCH", L, None)] + flat(3, 99, d=L)
    t = simulate({"XUSDT": series(rows)}, paper(), cost, WIN).trades[0]
    assert t.exit_reason == "stop_hit" and abs(t.stop_level - 99.0) < 1e-9  # fill 101 - 2 (raw anchor = 98)


def test_direction_exit_at_next_open_and_no_time_stop():
    rows = [(100, 100, 100, 100, "BUY", L, 5.0), (100, 101, 99, 100, "WATCH", L, None)]
    rows += [(100, 101, 99, 100, "WATCH", L, None)] * 60  # 60 bars: a 48-bar time-stop would have fired
    rows += [(100, 101, 99, 100, "WATCH", N, None), (103, 104, 102, 103, "WATCH", N, None)] + flat(2, 103)
    t = simulate({"XUSDT": series(rows)}, paper(), NOFEE, (T0, T0 + 100 * H)).trades[0]
    assert t.exit_reason == "direction_flipped" and t.exit_raw == 103 and t.exit_time == T0 + 63 * H


def test_min_fill_fraction_refuses_dust_lot():
    rows = {"A": [(100, 100, 100, 100, "BUY", L, 2.0), (100, 100, 100, 100, "BUY", L, 2.0)] + flat(3, d=L)}
    loose = dict(max_notional_pct=10.0, max_symbol_notional_pct=10.0, max_open_risk_pct=1.0)
    r = paper(risk_pct=0.04, **loose)  # intended notional 10 000, cash 5 000 -> 50 % >= 25 % -> accepted
    res = simulate({"A": series(rows["A"])}, r, NOFEE, WIN, initial=5000.0)
    assert res.open_at_end
    r2 = paper(risk_pct=0.10, **loose)  # intended 25 000 -> 20 % < 25 % -> refused
    res2 = simulate({"A": series(rows["A"])}, r2, NOFEE, WIN, initial=5000.0)
    assert not res2.open_at_end and res2.rejections["insufficient_cash"] == 1


def test_cost_by_symbol_is_applied_per_symbol():
    rows = [(100, 100, 100, 100, "BUY", L, 2.0), (100, 100, 100, 100, "BUY", L, 2.0),
            (100, 106, 100, 105, "WATCH", L, None)] + flat(3, 105, d=L)
    costs = {"A": CostModel("a", 0.0, 0.0, 0.0), "B": CostModel("b", 50.0, 0.0, 0.0)}
    res = simulate({"A": series(rows), "B": series(rows)}, paper(), NOFEE, WIN, cost_by_symbol=costs)
    by = {t.symbol: t for t in res.trades}
    assert by["A"].commission == 0 and by["B"].commission > 0


def test_excursions_exclude_unknown_part_of_exit_bar():
    rows = [(100, 100, 100, 100, "BUY", L, 2.0), (100, 101.5, 99.5, 101, "WATCH", L, None),
            (101, 103.9, 97.0, 98, "WATCH", L, None)] + flat(3, 98, d=L)  # stop bar with a high of 103.9
    t = simulate({"XUSDT": series(rows)}, paper(), NOFEE, WIN).trades[0]
    assert t.exit_reason == "stop_hit"
    assert t.high_seen == 101.5  # the stop bar's high is not counted (order unknown)
    assert t.low_seen == t.stop_level


def test_defaults_unchanged_for_earlier_runs():
    r = Rules("x")
    assert (r.levels_anchor, r.gate_equity, r.min_fill_fraction) == ("raw", "mark", 0.0)


# --- feed / diagnostic -------------------------------------------------------------------------------------------

def test_feed_warmup_until_live_window():
    n = LIVE_WINDOW_BARS + 2
    candles = [Candle(time=T0 + i * H, open=1, high=1, low=1, close=1, volume=1) for i in range(n)]
    sigs = [sig(T0 + i * H, "BUY", L, 1.0) for i in range(n)]
    feed = build_feed(candles, sigs)
    assert feed[T0 + (LIVE_WINDOW_BARS - 2) * H][1].decision == "WARMUP"
    assert feed[T0 + (LIVE_WINDOW_BARS - 1) * H][1].decision == "BUY"


def test_flags_on_a_stop_then_rebound_trade():
    rows = [(100, 100, 100, 100, "BUY", L, 2.0), (100, 102.5, 99.5, 101, "WATCH", L, None),
            (101, 101, 97, 98, "WATCH", L, None)] + [(98, 103, 97, 102, "WATCH", L, None)] * 30
    data = series(rows)
    res = simulate({"XUSDT": data}, paper(), NOFEE, (T0, T0 + 33 * H))
    candles = [data[t][0] for t in sorted(data)]
    r = dg.trade_rows(res.trades, {"XUSDT": dg.SeriesIndex(candles)},
                      {"XUSDT": {t: data[t][1] for t in data}})[0]
    assert abs(r["mfe_r"] - 1.25) < 1e-9  # high 102.5 vs entry 100, R = 2
    assert r["F4_stop_then_rebound"]  # after the stop, highs reach 103 >= entry + 1R = 102
    assert not r["F3_exit_then_continued"]  # F3 is for non-stop exits only
    assert r["F2_gave_back"]  # MFE >= 1R and gross <= 0
    assert not r["F1_entry_adverse"]
