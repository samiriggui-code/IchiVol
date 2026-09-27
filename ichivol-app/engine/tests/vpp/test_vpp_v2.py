"""VP-P v2 (amendement VP0-2026-09-28): tolerance, month bootstrap, event study, engine replay (C3)."""

import pytest
from sqlalchemy.exc import OperationalError

from app.agents.types import Direction
from app.indicators.ichimoku import Candle
from research_lab.signals import BarSignal
from research_lab.sim import CostModel

from vpp import LIVE_WINDOW_BARS
from vpp import diagnose as dg
from vpp import event_study as es

H = 3600
T0 = 1_704_067_200  # 2024-01-01 00:00 UTC
L, N = Direction.LONG, Direction.NEUTRAL


def test_r_threshold_tolerance_counts_float_targets():
    assert dg.ge_r(1.9999999999999498, 2.0) and not (1.9999999999999498 >= 2.0)
    assert not dg.ge_r(1.99, 2.0)
    assert dg.lt_r(0.49, 0.5) and not dg.lt_r(0.4999999999999, 0.5)


def test_month_cluster_ci_mean_and_bounds():
    items = [("2024-01", 1.0), ("2024-01", 3.0), ("2024-02", 2.0), ("2024-03", 2.0)]
    ci = dg.month_cluster_ci(items, n_boot=2000)
    assert ci["n"] == 4 and ci["months"] == 3 and ci["mean"] == 2.0
    assert ci["lo"] <= 2.0 <= ci["hi"]
    const = dg.month_cluster_ci([("2024-01", 5.0), ("2024-02", 5.0)], n_boot=500)
    assert const["lo"] == const["hi"] == 5.0


def _series(n, close=lambda i: 100.0 + i * 0.01):
    return [Candle(time=T0 + i * H, open=close(i), high=close(i), low=close(i), close=close(i), volume=1.0)
            for i in range(n)]


def _sig(t, d="WATCH", dr=N):
    return BarSignal(t, d, dr, 1.0, 1.0, (), (), "x", None)


def test_series_start_events_skip_repeats_and_warmup():
    n = LIVE_WINDOW_BARS + 20
    c = _series(n)
    s = [_sig(x.time) for x in c]
    k = LIVE_WINDOW_BARS + 2
    for i in (5, k, k + 1, k + 2, k + 6):  # 5 = warm-up (ignored); k..k+2 = one series; k+6 = new series
        s[i] = _sig(c[i].time, "BUY", L)
    win = (c[0].time, c[-1].time + H)
    ev = es.events({"X": s}, {"X": c}, win, "series_start")
    assert ev == [("X", k), ("X", k + 6)]
    assert len(es.events({"X": s}, {"X": c}, win, "all")) == 4


def test_return_definition_next_open_to_close_h():
    c = _series(10, close=lambda i: float(100 + i))
    assert es._ret(c, 2, 3) == c[5].close / c[3].open - 1
    assert es._ret(c, 8, 3) is None  # window leaves the data: excluded, never extrapolated


def test_study_controls_come_from_same_symbol_and_month():
    # a month of flat prices except the event path: the control mean must be ~0, the difference ~ the event return
    n = LIVE_WINDOW_BARS + 24 * 40
    c = _series(n, close=lambda i: 100.0)
    ev_i = LIVE_WINDOW_BARS + 24 * 5
    bump = [Candle(time=x.time, open=x.open, high=x.high, low=x.low, close=x.close * (1.1 if j > ev_i else 1.0),
                   volume=1.0) for j, x in enumerate(c)]
    cost = {"X": CostModel("c", 7.5, 1.0, 0.0)}
    win = (bump[LIVE_WINDOW_BARS].time, bump[-1].time + H)
    out = es.study([("X", ev_i)], {"X": bump}, win, cost, cost, with_ci=False)
    r24 = out["24"]
    assert r24["n"] == 1
    assert r24["r"]["mean_pct"] == pytest.approx(10.0, abs=1e-9)  # open(t+1) is unbumped (100), close(t+24) = 110
    assert r24["net"]["mean_pct"] == pytest.approx(r24["r"]["mean_pct"] - 2 * 8.5 / 100, abs=1e-9)


# --- C3 engine replay (real paper engine, dev Postgres) ---------------------------------------------------------

try:
    from app.db.session import engine as _db

    with _db.connect():
        pass
    DB = True
except (OperationalError, Exception):
    DB = False


@pytest.mark.skipif(not DB, reason="dev Postgres not reachable")
def test_engine_replay_matches_simulator_on_a_small_life_cycle():
    from vpp.replay import compare_window

    def feed(rows):
        out = {}
        for i, (o, h, l, c, d, dr, sd) in enumerate(rows):
            t = T0 + i * H
            out[t] = (Candle(time=t, open=o, high=h, low=l, close=c, volume=1e6), BarSignal(t, d, dr, sd, 1.0, (), (), "x", None))
        return out

    warm = [(100, 100, 100, 100, "WARMUP", N, None)] * (LIVE_WINDOW_BARS - 1)
    a = warm + [(100, 100, 100, 100, "BUY", L, 2.0), (100, 101, 99.5, 100.5, "WATCH", L, None),
                (100.5, 104.5, 100, 104, "WATCH", L, None)] + [(104, 104, 104, 104, "WATCH", L, None)] * 5
    b = warm + [(50, 50, 50, 50, "BUY", L, 1.0), (50, 50.5, 49.8, 50, "WATCH", L, None),
                (50, 50.2, 48.5, 49, "WATCH", L, None)] + [(49, 49, 49, 49, "WATCH", L, None)] * 5
    cc = warm + [(10, 10, 10, 10, "BUY", L, 0.3), (10, 10.1, 9.9, 10, "WATCH", L, None),
                 (10, 10.1, 9.9, 10.05, "WATCH", N, None), (10.2, 10.2, 10.2, 10.2, "WATCH", N, None)] + \
        [(10.2, 10.2, 10.2, 10.2, "WATCH", N, None)] * 4
    feeds = {"AAAUSDT": feed(a), "BBBUSDT": feed(b), "CCCUSDT": feed(cc)}
    w = (T0 + (LIVE_WINDOW_BARS - 1) * H, T0 + (LIVE_WINDOW_BARS + 8) * H)
    res = compare_window(feeds, w)
    assert res["sim_trades"] == res["engine_trades"] == 3
    assert res["matched_ok"] == 3, res["differences"]
    assert res["max_qty_rel"] < 1e-9 and res["max_stop_rel"] < 1e-9
    assert res["max_realized_abs_eur"] < 1e-6
    assert res["equity_end_rel_diff"] < 1e-9
