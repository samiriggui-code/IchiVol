"""Accounting/execution rules of the closed-candle research simulator."""
from decimal import Decimal

from app.agents.types import Direction
from app.indicators.ichimoku import Candle
from research_lab.sim import BASE_COST, CostModel, Rules, simulate
from research_lab.signals import BarSignal

H = 3600
T0 = 1_700_000_000 - 1_700_000_000 % H
NOFEE = CostModel("nofee", 0.0, 0.0, 0.0)


def sig(t, decision="WATCH", direction=Direction.NEUTRAL, sd=None):
    return BarSignal(t, decision, direction, sd, 1.0, (), (), "signal" if decision in ("BUY", "SELL") else "x", None)


def bar(i, o, h, l, c, v=1e6):
    return Candle(time=T0 + i * H, open=o, high=h, low=l, close=c, volume=v)


def series(rows):
    """rows: list of (o,h,l,c,decision,sd). BUY rows imply LONG direction."""
    out = {}
    for i, (o, h, l, c, d, sd) in enumerate(rows):
        direction = Direction.LONG if d == "BUY" else Direction.SHORT if d == "SELL" else Direction.NEUTRAL
        out[T0 + i * H] = (bar(i, o, h, l, c), sig(T0 + i * H, d, direction, sd))
    return out


WIN = (T0, T0 + 50 * H)
R = Rules("t", daily_loss_limit_pct=0.0)


def run(rows, cost=NOFEE, rules=R):
    return simulate({"XUSDT": series(rows)}, rules, cost, WIN)


def flat(n, px=100.0):
    return [(px, px, px, px, "WATCH", None)] * n


def test_entry_at_next_open_and_stop_fill_at_level():
    rows = [(100, 100, 100, 100, "BUY", 2.0), (101, 101, 101, 101, "BUY", 2.0), (101, 101, 97, 98, "WATCH", None)] + flat(3)
    res = run(rows)
    t = res.trades[0]
    assert t.entry_raw == 101 and t.entry_time == T0 + H  # next open, not the signal bar's close
    assert t.exit_reason == "stop_hit" and t.exit_raw == 99  # stop = 101 - 2, filled AT the level
    assert res.ledger_diff == {}


def test_costs_counted_once_and_net_reconciles_with_cash():
    rows = [(100, 100, 100, 100, "BUY", 2.0), (100, 100, 100, 100, "BUY", 2.0), (100, 100, 100, 100, "WATCH", None)] + flat(3)
    res = run(rows, cost=BASE_COST)
    t = res.trades[0]
    assert abs(t.net - (t.gross - t.commission - t.friction_cost)) < 1e-6  # spread/slippage only via fills
    assert abs(res.cash_end - (5000 + sum(x.net for x in res.trades))) < 1e-6
    assert res.ledger_diff == {} or all(abs(Decimal(v)) < Decimal("1e-6") for v in res.ledger_diff.values())


def test_stop_first_when_stop_and_target_in_same_bar():
    rows = [(100, 100, 100, 100, "BUY", 2.0), (100, 100, 100, 100, "BUY", 2.0), (100, 106, 96, 100, "BUY", None)] + flat(3)
    t = run(rows).trades[0]
    assert t.exit_reason == "stop_hit_ambiguous"


def test_gap_beyond_stop_fills_at_open_not_at_level():
    rows = [(100, 100, 100, 100, "BUY", 2.0), (100, 100, 100, 100, "BUY", 2.0), (90, 91, 89, 90, "WATCH", None)] + flat(3, 90)
    t = run(rows).trades[0]
    assert t.exit_reason == "stop_hit_gap" and t.exit_raw == 90 and t.stop_gap


def test_entry_bar_range_before_open_is_never_used():
    # entry bar opens at 100 (stop 98); its low 97 is AFTER the open -> counts; but the SIGNAL bar's low must not
    rows = [(100, 100, 90, 100, "BUY", 2.0), (100, 101, 99, 100, "BUY", 2.0), (100, 101, 99, 100, "WATCH", None)] + flat(3)
    t = run(rows).trades[0]
    assert t.exit_reason == "pipeline_downgraded"  # the 90 low of the signal bar did not trigger the stop


def test_signal_run_is_traded_once_after_stop_out():
    rows = [(100, 100, 100, 100, "BUY", 2.0), (100, 100, 100, 100, "BUY", 2.0), (100, 100, 96, 97, "BUY", 2.0)] + [
        (97, 97, 97, 97, "BUY", 2.0)
    ] * 5
    res = run(rows)
    assert len(res.trades) == 1 and res.rejections["signal_already_processed"] >= 1


def test_open_risk_cap_rejects_second_position():
    d = {"AUSDT": series([(100, 100, 100, 100, "BUY", 2.0)] * 6), "BUSDT": series([(100, 100, 100, 100, "BUY", 2.0)] * 6)}
    res = simulate(d, Rules("t", max_open_risk_pct=0.006, daily_loss_limit_pct=0.0), NOFEE, WIN)
    assert res.rejections["open_risk_cap"] >= 1
    assert len(res.open_at_end) == 1


def test_deterministic():
    rows = [(100, 100, 100, 100, "BUY", 2.0), (100, 106, 100, 105, "BUY", 2.0)] + flat(4)
    assert [t.net for t in run(rows).trades] == [t.net for t in run(rows).trades]
