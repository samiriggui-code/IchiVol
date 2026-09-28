"""RS-D1 — contrôles d'implémentation exigés avant le run (RS-03 §10)."""

from __future__ import annotations

import random
from datetime import datetime, timezone

import pytest

from app.indicators.ichimoku import Candle
from rs import (
    BAR_SECONDS,
    DATA_END_EXCL,
    ENTRY_PERIOD,
    INITIAL_CAPITAL,
    MAX_NOTIONAL_PCT,
    RISK_PCT,
    STOP_ATR_MULT,
)
from rs.baselines import passive
from rs.costs import SymbolCost, cost_profile
from rs.data import truncate
from rs.donchian import simulate, size_entry
from rs.metrics import boot_mean_ci, max_drawdown, monthly_returns

T0 = int(datetime(2021, 1, 1, tzinfo=timezone.utc).timestamp())
NOFEE = {s: SymbolCost(0.0, 0.0) for s in ("BTCUSDT", "ETHUSDT", "SOLUSDT", "X")}


def _c(i: int, o: float, h: float, l: float, c: float) -> Candle:
    return Candle(time=T0 + i * BAR_SECONDS, open=o, high=h, low=l, close=c, volume=1.0)


def _flat(n: int, px: float = 100.0, half: float = 0.5) -> list[Candle]:
    return [_c(i, px, px + half, px - half, px) for i in range(n)]


def _breakout_series(after: list[tuple[float, float, float, float]]) -> list[Candle]:
    """60 barres plates à 100 (U55 = 100.5), barre 60 = cassure (close 110), puis ``after``."""
    bars = _flat(60)
    bars.append(_c(60, 100.0, 110.5, 99.5, 110.0))
    for k, (o, h, l, c) in enumerate(after):
        bars.append(_c(61 + k, o, h, l, c))
    return bars


def _run(bars: list[Candle], **kw):
    return simulate({"X": bars}, NOFEE, score_start=T0, **kw)


def _atr_at_breakout() -> float:
    # 13 TR plates de 1.0 + TR cassure = 110.5 − 99.5 = 11.0 → moyenne simple 14
    return (13 * 1.0 + 11.0) / 14


# --- entrée -----------------------------------------------------------------------------------


def test_entry_signal_at_close_fills_next_open():
    bars = _breakout_series([(111.0, 112.0, 110.5, 111.5)] * 3)
    out = _run(bars)
    assert out.orders[0] == (bars[60].time, "X", "entry")
    tr = out.trades[0]
    assert tr.signal_time == bars[60].time
    assert tr.entry_time == bars[61].time
    assert tr.entry_raw == 111.0


def test_no_entry_before_55_bars_of_history():
    bars = _flat(40)
    bars.append(_c(40, 100.0, 150.0, 99.5, 150.0))
    bars += [_c(41 + k, 150.0, 151.0, 149.0, 150.0) for k in range(5)]
    assert _run(bars).orders == []


# --- stop -------------------------------------------------------------------------------------


def test_initial_stop_anchored_on_fill_with_signal_atr():
    bars = _breakout_series([(111.0, 112.0, 110.5, 111.5)] * 3)
    tr = _run(bars).trades[0]
    assert tr.initial_stop == pytest.approx(111.0 - STOP_ATR_MULT * _atr_at_breakout())


def test_trailing_stop_is_monotone_and_applies_from_next_bar():
    # hausse puis repli : le stop monte puis ne redescend jamais
    after = [(111.0, 121.0, 110.8, 120.0), (120.0, 131.0, 119.5, 130.0), (130.0, 130.5, 124.0, 125.0),
             (125.0, 126.0, 123.0, 124.0)]
    out = _run(_breakout_series(after))
    stops = [s for _, s in out.stop_log["X"]]
    assert stops == sorted(stops)
    assert stops[1] > stops[0]


def test_stop_raised_at_close_k_not_hit_on_bar_k():
    # barre 61 : low 110.8 ; à sa clôture (120) le stop monte au-dessus de 110.8 → pas de sortie en 61.
    after = [(111.0, 121.0, 110.8, 120.0), (120.0, 120.5, 119.0, 119.5)]
    out = _run(_breakout_series(after))
    t61 = _breakout_series(after)[61].time
    assert out.stop_log["X"][0][0] == t61
    raised = out.stop_log["X"][0][1]
    assert raised > 110.8
    tr = out.trades[0]
    assert tr.exit_reason in ("open_at_end", "stop_trail")
    assert tr.exit_time != t61


def test_gap_below_stop_exits_at_open():
    atr = _atr_at_breakout()
    stop0 = 111.0 - STOP_ATR_MULT * atr
    gap_open = stop0 - 3.0
    after = [(111.0, 112.0, 110.5, 111.5), (gap_open, gap_open + 0.5, gap_open - 1, gap_open)]
    tr = _run(_breakout_series(after)).trades[0]
    assert tr.exit_reason == "stop_gap"
    assert tr.exit_raw == gap_open


def test_intrabar_stop_exits_at_stop_price():
    atr = _atr_at_breakout()
    stop0 = 111.0 - STOP_ATR_MULT * atr
    after = [(111.0, 112.0, 110.5, 111.0), (111.0, 111.5, stop0 - 1.0, 110.0)]
    out = _run(_breakout_series(after))
    tr = out.trades[0]
    # la clôture de 61 (111) ne relève pas le stop au-dessus de stop0 − (le max close reste 111)
    assert tr.exit_reason in ("stop_initial", "stop_trail")
    assert tr.exit_raw == pytest.approx(out.stop_log["X"][0][1])


# --- sortie de canal / réentrée ---------------------------------------------------------------


def _channel_series() -> list[Candle]:
    """Entrée large ATR (stop loin), puis close sous L20 sans toucher le stop."""
    bars = [_c(i, 100.0, 104.0, 96.0, 100.0) for i in range(60)]  # ATR ≈ 8 → stop à ~24 sous l'entrée
    bars.append(_c(60, 100.0, 106.0, 99.0, 105.0))  # cassure U55 = 104
    bars.append(_c(61, 105.0, 106.0, 104.0, 105.0))
    bars.append(_c(62, 105.0, 105.5, 94.0, 95.0))  # close 95 < L20 (= 96) → sortie à open(63)
    bars.append(_c(63, 94.5, 95.0, 94.0, 94.8))
    bars.append(_c(64, 94.8, 95.0, 94.5, 94.9))
    return bars


def test_channel_exit_at_next_open():
    bars = _channel_series()
    out = _run(bars)
    tr = out.trades[0]
    assert (bars[62].time, "X", "exit") in out.orders
    assert tr.exit_reason == "channel"
    assert tr.exit_time == bars[63].time
    assert tr.exit_raw == 94.5


def test_channel_exit_delayed_with_exec_delay_2():
    bars = _channel_series()
    tr = _run(bars, exec_delay=2).trades[0]
    assert tr.exit_time == bars[64].time


def test_no_reentry_on_exit_bar():
    # sortie par stop intrabarre sur la barre 62, dont la clôture recasse U55 → pas d'entrée décidée en 62
    atr = _atr_at_breakout()
    stop0 = 111.0 - STOP_ATR_MULT * atr
    after = [(111.0, 112.0, 110.5, 111.0), (111.0, 125.0, stop0 - 1.0, 124.0), (124.0, 127.5, 123.5, 127.0)]
    bars = _breakout_series(after)
    out = _run(bars)
    assert out.trades[0].exit_time == bars[62].time
    assert (bars[62].time, "X", "entry") not in out.orders
    assert out.rejections.get("reentry_same_bar") == 1
    assert (bars[63].time, "X", "entry") in out.orders


# --- taille / coûts ---------------------------------------------------------------------------


def test_size_risk_half_percent_when_under_cap():
    c = SymbolCost(0.0, 0.0)
    qty, notional, _ = size_entry(5000.0, 5000.0, 100.0, 20.0, c)
    assert qty * 20.0 == pytest.approx(5000.0 * RISK_PCT)
    assert notional < 5000.0 * MAX_NOTIONAL_PCT


def test_size_capped_at_ten_percent():
    c = SymbolCost(0.0, 0.0)
    qty, notional, _ = size_entry(5000.0, 5000.0, 100.0, 1.0, c)
    assert notional == pytest.approx(5000.0 * MAX_NOTIONAL_PCT)


def test_size_limited_by_cash_and_refused_under_quarter():
    c = SymbolCost(7.5, 0.0)
    # visé 500 ; cash 200 → exécuté à hauteur du cash
    qty, notional, fee = size_entry(5000.0, 200.0, 100.0, 1.0, c)
    assert notional + fee == pytest.approx(200.0)
    # cash 100 < 25 % de 500 → refusé
    assert size_entry(5000.0, 100.0, 100.0, 1.0, c) == "insufficient_cash"


def test_size_min_notional_and_invalid_stop():
    c = SymbolCost(0.0, 0.0)
    assert size_entry(100.0, 100.0, 100.0, 50.0, c) == "below_min_notional"
    assert size_entry(5000.0, 5000.0, 10.0, 10.0, c) == "invalid_stop"


def test_cost_profiles_per_symbol():
    paper = cost_profile("paper")
    assert paper["BTCUSDT"] == SymbolCost(7.5, 1.0)
    assert paper["SOLUSDT"] == SymbolCost(7.5, 1.5)
    adv = cost_profile("adverse")
    assert adv["BTCUSDT"] == SymbolCost(10.0, 4.0 + 8.0)
    assert adv["SOLUSDT"] == SymbolCost(10.0, 4.0 + 8.0)
    assert paper["SOLUSDT"].fill(100.0, "buy") == pytest.approx(100.015)
    assert paper["SOLUSDT"].fill(100.0, "sell") == pytest.approx(99.985)
    assert paper["BTCUSDT"].fee(1000.0) == pytest.approx(0.75)


def test_trade_net_includes_fees_and_friction():
    costs = {"X": SymbolCost(7.5, 1.0)}
    bars = _channel_series()
    tr = simulate({"X": bars}, costs, score_start=T0).trades[0]
    assert tr.entry_fill == pytest.approx(105.0 * 1.0001)
    assert tr.exit_fill == pytest.approx(94.5 * 0.9999)
    assert tr.net == pytest.approx(tr.qty * tr.exit_fill - tr.notional - tr.fees)


# --- garde-fou 2025 / troncature --------------------------------------------------------------


def test_truncate_drops_2025_and_simulate_asserts():
    last = Candle(time=DATA_END_EXCL - BAR_SECONDS, open=1, high=1, low=1, close=1, volume=1)
    reserved = Candle(time=DATA_END_EXCL, open=1, high=1, low=1, close=1, volume=1)
    assert truncate([last, reserved]) == [last]
    with pytest.raises(AssertionError):
        simulate({"X": [last, reserved]}, NOFEE)


def _random_walk(n: int, seed: int, start: float = 100.0) -> list[Candle]:
    rng = random.Random(seed)
    px = start
    out = []
    for i in range(n):
        o = px
        c = max(1.0, o * (1 + rng.gauss(0.001, 0.02)))
        h = max(o, c) * (1 + abs(rng.gauss(0, 0.005)))
        l = min(o, c) * (1 - abs(rng.gauss(0, 0.005)))
        out.append(_c(i, o, h, l, c))
        px = c
    return out


@pytest.mark.parametrize("cut", [150, 233, 377, 480])
def test_strategy_truncation_invariance(cut):
    """Freqtrade-style : signaux, stops et ordres jusqu'à T identiques, que la série continue ou non."""
    full = {s: _random_walk(520, seed) for s, seed in (("BTCUSDT", 1), ("ETHUSDT", 2), ("SOLUSDT", 3))}
    t_cut = T0 + cut * BAR_SECONDS
    part = {s: [c for c in v if c.time <= t_cut] for s, v in full.items()}
    costs = cost_profile("paper")
    a = simulate(full, costs, score_start=T0)
    b = simulate(part, costs, score_start=T0)
    assert [o for o in a.orders if o[0] <= t_cut] == b.orders
    for s in full:
        assert [x for x in a.stop_log[s] if x[0] <= t_cut] == b.stop_log[s]
    closed_a = [t for t in a.trades if t.exit_time is not None and t.exit_time <= t_cut]
    closed_b = [t for t in b.trades if t.exit_time is not None]
    assert closed_a == closed_b
    assert [e for e in a.equity if e[0] <= t_cut] == b.equity
    assert len(a.orders) > len(b.orders) or cut >= 480


def test_open_positions_valued_at_end_without_forced_sale():
    bars = _breakout_series([(111.0, 112.0, 110.5, 111.5)] * 3)
    out = _run(bars)
    tr = out.trades[-1]
    assert tr.exit_reason == "open_at_end" and tr.exit_time is None
    assert out.equity[-1][1] == pytest.approx(INITIAL_CAPITAL - tr.notional + tr.qty * 111.5)


# --- références passives ----------------------------------------------------------------------


def _monthly(n_days: int, prices: dict[str, float], jump: dict[str, tuple[int, float]] | None = None):
    """Barres 4h sur ``n_days`` jours, prix constant par symbole ; ``jump`` = {sym: (jour, nouveau prix)}."""
    out = {}
    for s, p in prices.items():
        bars = []
        for i in range(n_days * 6):
            px = p
            if jump and s in jump and i >= jump[s][0] * 6:
                px = jump[s][1]
            bars.append(Candle(time=T0 + i * BAR_SECONDS, open=px, high=px, low=px, close=px, volume=1))
        out[s] = bars
    return out


def test_b0f_fully_invested_no_leverage_and_marked_at_close():
    data = _monthly(40, {"A": 100.0, "B": 50.0}, jump={"A": (10, 200.0)})
    costs = {"A": SymbolCost(7.5, 1.0), "B": SymbolCost(7.5, 1.0)}
    eq = passive(data, costs, weight=1.0, rebalance_monthly=False, score_start=T0)
    e0 = eq[0]
    assert e0[1] - e0[2] >= -1e-9  # cash ≥ 0
    assert e0[2] / e0[1] > 0.998
    # A double → la moitié du panier double
    assert eq[-1][1] == pytest.approx(e0[2] / 2 * 2 + e0[2] / 2 + (e0[1] - e0[2]), rel=1e-3)


def test_b0e_rebalanced_monthly_to_weight():
    data = _monthly(70, {"A": 100.0, "B": 100.0}, jump={"A": (5, 150.0)})
    eq = passive(data, {"A": SymbolCost(0, 0), "B": SymbolCost(0, 0)}, weight=0.3, rebalance_monthly=True,
                 score_start=T0)
    assert eq[0][2] / eq[0][1] == pytest.approx(0.3)
    feb1 = int(datetime(2021, 2, 1, tzinfo=timezone.utc).timestamp())
    row = next(r for r in eq if r[0] == feb1)
    assert row[2] / row[1] == pytest.approx(0.3)
    before = next(r for r in eq if r[0] == feb1 - BAR_SECONDS)
    assert before[2] / before[1] > 0.3


# --- métriques --------------------------------------------------------------------------------


def test_monthly_returns_and_drawdown():
    jan = int(datetime(2021, 1, 31, tzinfo=timezone.utc).timestamp())
    feb = int(datetime(2021, 2, 28, tzinfo=timezone.utc).timestamp())
    eq = [(jan, 110.0, 0.0), (feb, 99.0, 0.0)]
    m = monthly_returns(eq, 100.0)
    assert m == {"2021-01": pytest.approx(0.10), "2021-02": pytest.approx(-0.10)}
    dd = max_drawdown(eq)
    assert dd["max_dd"] == pytest.approx(-0.10) and dd["recovery_days"] is None


def test_bootstrap_deterministic_and_brackets_mean():
    vals = [0.01, -0.02, 0.03, 0.0, 0.015, -0.005]
    a, b = boot_mean_ci(vals, n=2000), boot_mean_ci(vals, n=2000)
    assert a == b
    assert a["lo"] <= a["mean"] <= a["hi"]


def test_entry_period_constant_is_55():
    assert ENTRY_PERIOD == 55


# --- validation 2025 (VP0-2026-09-28c) --------------------------------------------------------


def test_validation_truncation_is_2026_and_default_stays_2025():
    from rs import VAL_DATA_END_EXCL

    y25 = Candle(time=DATA_END_EXCL, open=1, high=1, low=1, close=1, volume=1)
    y26 = Candle(time=VAL_DATA_END_EXCL, open=1, high=1, low=1, close=1, volume=1)
    assert truncate([y25, y26], VAL_DATA_END_EXCL) == [y25]
    with pytest.raises(AssertionError):
        simulate({"X": [y25]}, NOFEE)  # défaut : 2025 interdit
    with pytest.raises(AssertionError):
        simulate({"X": [y25, y26]}, NOFEE, data_end_excl=VAL_DATA_END_EXCL)


def test_validation_verdict_rules():
    from rs.validate import validation_verdict

    base = {"net_return": 0.05, "max_dd": -0.04, "calmar": 1.2}
    adv = {"net_return": 0.02}
    b0e_up = {"cagr": 0.03, "calmar": 0.5, "net_return": 0.03}
    b0e_down = {"cagr": -0.02, "calmar": -0.3, "net_return": -0.02}
    assert validation_verdict(base, adv, b0e_up, 40)["verdict"] == "VALIDÉ 2025"
    assert validation_verdict(base, adv, b0e_down, 40)["v4_rule"].startswith("net_return")
    assert validation_verdict(base, adv, b0e_up, 5)["verdict"] == "NON CONCLUANT"
    assert validation_verdict({**base, "net_return": -0.01}, adv, b0e_up, 40)["verdict"] == "ÉCHEC"
    assert validation_verdict({**base, "max_dd": -0.2}, adv, b0e_up, 40)["verdict"] == "ÉCHEC"
