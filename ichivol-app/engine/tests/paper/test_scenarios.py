"""T0-CALC scenario calculator — unit tests (no Postgres)."""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace as NS

import pytest

from app.backtest.engine import BacktestResult, Trade
from app.backtest.metrics import Metrics
from app.agents.types import Direction
from app.indicators.ichimoku import Candle
from app.paper.risk import apply_entry_friction, apply_exit_friction
from app.paper.scenarios import (
    EXPECTANCY_MIN_N,
    build_open_position_scenarios,
    build_scenarios,
    closed_candles,
    worst_adverse_long,
)
from app.paper.strategy_profiles import BASELINE_PROFILE


def _candle(t: int, o: float, h: float, l: float, c: float) -> Candle:
    return Candle(time=t, open=o, high=h, low=l, close=c, volume=1.0)


def _hist_with_crash() -> list[Candle]:
    """Closed history where bar at t=200 has a -20% low vs prev close (and a milder gap)."""
    return [
        _candle(100, 100, 101, 99, 100),
        _candle(200, 98, 99, 80, 90),  # low/prev = 0.80 → -20%; gap = -2%
        _candle(300, 90, 95, 88, 92),
        _candle(400, 92, 96, 91, 95),
    ]


def _preview_like_outcomes(*, price: float, notional: float, stop_pct: float, tp_r: float, symbol: str = "BTCUSDT"):
    """Reproduce preview_manual_buy outcome math (LONG) for equality assertions."""
    profile = dict(BASELINE_PROFILE)
    from app.paper.broker import _commission_bps, _friction
    from app.paper.risk import size_position

    spread_bps, slip_bps = _friction(profile, symbol)
    comm_bps = _commission_bps(profile, symbol)
    stop_distance = price * stop_pct
    sized = size_position(
        equity=10_000.0,
        cash=10_000.0,
        direction="LONG",
        entry_price=price,
        stop_distance=stop_distance,
        take_profit_r=tp_r,
        commission_bps=comm_bps,
        spread_bps=spread_bps,
        slippage_bps=slip_bps,
        min_notional=10.0,
        manual_notional=notional,
    )
    assert sized is not None
    qty, entry_fill, stop_price, tp_price = sized.qty, sized.entry_fill, sized.stop_price, sized.take_profit_price
    entry_fee = qty * entry_fill * comm_bps / 10_000.0
    exit_at_tp = apply_exit_friction(tp_price, direction="LONG", spread_bps=spread_bps, slippage_bps=slip_bps)
    exit_at_stop = apply_exit_friction(stop_price, direction="LONG", spread_bps=spread_bps, slippage_bps=slip_bps)
    fee_tp = qty * exit_at_tp * comm_bps / 10_000.0
    fee_stop = qty * exit_at_stop * comm_bps / 10_000.0
    gain = qty * (exit_at_tp - entry_fill) - entry_fee - fee_tp
    loss = qty * (exit_at_stop - entry_fill) - entry_fee - fee_stop
    return {
        "qty": qty,
        "entry_fill": entry_fill,
        "stop_price": stop_price,
        "take_profit_price": tp_price,
        "notional": qty * entry_fill,
        "entry_fee": entry_fee,
        "net_gain_if_target": gain,
        "net_loss_if_stop": loss,
        "profile": profile,
        "symbol": symbol,
    }


def _fake_pipeline(*, n_trades: int, expectancy: float = -0.01, win_rate: float = 0.4) -> dict:
    trades: list[Trade] = []
    t0 = 1_700_000_000
    for i in range(n_trades):
        # alternate winners/losers roughly matching win_rate
        win = (i / max(n_trades, 1)) < win_rate
        lr = 0.02 if win else -0.015
        trades.append(
            Trade(
                entry_time=t0 + i * 7200,
                exit_time=t0 + i * 7200 + 3600 * (4 if win else 2),
                direction=Direction.LONG,
                entry_price=100.0,
                exit_price=102.0 if win else 98.5,
                log_return=lr,
                cost_log=0.001,
            )
        )
    bt = BacktestResult(
        symbol="BTCUSDT",
        timeframe="1h",
        n_bars=500,
        bar_returns=[0.0] * 500,
        posn=[Direction.NEUTRAL] * 500,
        trades=trades,
        commission_bps=5.0,
        slippage_bps=3.0,
        eod_return=0.0,
    )
    metrics = Metrics(
        n_bars=500,
        total_return=-0.05,
        cagr=None,
        sharpe=None,
        sortino=None,
        max_drawdown=0.1,
        num_trades=n_trades,
        win_rate=win_rate,
        profit_factor=0.9,
        expectancy=expectancy,
        exposure=0.5,
        win_rate_gross=win_rate,
        profit_factor_gross=1.0,
        expectancy_gross=expectancy,
    )
    return {
        "backtest": bt,
        "metrics": metrics,
        "candles": _hist_with_crash(),
        "n_bars": 4,
        "from_ts": 100,
        "to_ts": 400,
    }


def test_closed_candles_drops_forming_bar():
    now = 1000.0
    # 1h bar opened at 500 still open at t=1000 (closes at 500+3600=4100)
    candles = [_candle(100, 1, 1, 1, 1), _candle(500, 1, 1, 1, 1)]
    out = closed_candles(candles, "1h", now=now)
    assert len(out) == 1
    assert out[0].time == 100


def test_worst_adverse_matches_real_candle():
    hist = _hist_with_crash()
    ref = worst_adverse_long(hist)
    assert ref is not None
    assert ref["time"] == 200
    assert ref["kind"] == "low"
    assert ref["move"] == pytest.approx(80 / 100 - 1.0)
    assert ref["value"] == 80.0


def test_crash_loss_at_least_stop_loss():
    o = _preview_like_outcomes(price=100.0, notional=1000.0, stop_pct=0.02, tp_r=2.0)
    scen = build_scenarios(
        o["symbol"],
        "1h",
        o["entry_fill"],
        o["qty"],
        o["stop_price"],
        o["take_profit_price"],
        o["profile"],
        net_gain_if_target=o["net_gain_if_target"],
        net_loss_if_stop=o["net_loss_if_stop"],
        invested=o["notional"],
        equity=10_000.0,
        entry_fee=o["entry_fee"],
        candles=_hist_with_crash(),
        pipeline_payload=_fake_pipeline(n_trades=5),
    )
    # perte crash ≥ perte stop  ⇒  net crash ≤ net stop (both ≤ 0)
    assert scen["crash"]["net_eur"] <= scen["stop"]["net_eur"] + 1e-9
    assert scen["crash"]["reference"]["candle_time"] == 200
    assert scen["crash"]["reference"]["move"] == pytest.approx(-0.20)


def test_target_stop_identical_to_preview_outcomes():
    o = _preview_like_outcomes(price=100.0, notional=500.0, stop_pct=0.03, tp_r=1.5)
    scen = build_scenarios(
        o["symbol"],
        "1h",
        o["entry_fill"],
        o["qty"],
        o["stop_price"],
        o["take_profit_price"],
        o["profile"],
        net_gain_if_target=o["net_gain_if_target"],
        net_loss_if_stop=o["net_loss_if_stop"],
        invested=o["notional"],
        equity=10_000.0,
        entry_fee=o["entry_fee"],
        candles=_hist_with_crash(),
        pipeline_payload=_fake_pipeline(n_trades=5),
    )
    assert scen["target"]["net_eur"] == pytest.approx(o["net_gain_if_target"])
    assert scen["stop"]["net_eur"] == pytest.approx(o["net_loss_if_stop"])


def test_expectancy_hidden_when_n_lt_30():
    o = _preview_like_outcomes(price=100.0, notional=1000.0, stop_pct=0.02, tp_r=2.0)
    scen = build_scenarios(
        o["symbol"],
        "1h",
        o["entry_fill"],
        o["qty"],
        o["stop_price"],
        o["take_profit_price"],
        o["profile"],
        net_gain_if_target=o["net_gain_if_target"],
        net_loss_if_stop=o["net_loss_if_stop"],
        invested=o["notional"],
        equity=10_000.0,
        entry_fee=o["entry_fee"],
        candles=_hist_with_crash(),
        pipeline_payload=_fake_pipeline(n_trades=EXPECTANCY_MIN_N - 1, expectancy=-0.01),
    )
    assert scen["expectancy"]["available"] is False
    assert scen["expectancy"]["expectancy_eur"] is None
    assert "échantillon insuffisant" in scen["expectancy"]["message"]
    assert str(EXPECTANCY_MIN_N - 1) in scen["expectancy"]["message"]


def test_expectancy_shown_when_n_ge_30():
    o = _preview_like_outcomes(price=100.0, notional=1000.0, stop_pct=0.02, tp_r=2.0)
    exp = -0.012
    scen = build_scenarios(
        o["symbol"],
        "1h",
        o["entry_fill"],
        o["qty"],
        o["stop_price"],
        o["take_profit_price"],
        o["profile"],
        net_gain_if_target=o["net_gain_if_target"],
        net_loss_if_stop=o["net_loss_if_stop"],
        invested=o["notional"],
        equity=10_000.0,
        entry_fee=o["entry_fee"],
        candles=_hist_with_crash(),
        pipeline_payload=_fake_pipeline(n_trades=EXPECTANCY_MIN_N, expectancy=exp, win_rate=0.45),
    )
    assert scen["expectancy"]["available"] is True
    assert scen["expectancy"]["n"] == EXPECTANCY_MIN_N
    assert scen["expectancy"]["expectancy_eur"] == pytest.approx(exp * o["notional"])
    assert scen["backtest_window"]["metrics_basis"] == "net_v2"


def test_financing_zero_crypto_positive_xau():
    o_btc = _preview_like_outcomes(price=100.0, notional=1000.0, stop_pct=0.02, tp_r=2.0, symbol="BTCUSDT")
    payload = _fake_pipeline(n_trades=40)
    # Force median hours via trades (winners 4h, losers 2h — overall median depends on mix)
    scen_btc = build_scenarios(
        "BTCUSDT",
        "1h",
        o_btc["entry_fill"],
        o_btc["qty"],
        o_btc["stop_price"],
        o_btc["take_profit_price"],
        o_btc["profile"],
        net_gain_if_target=o_btc["net_gain_if_target"],
        net_loss_if_stop=o_btc["net_loss_if_stop"],
        invested=o_btc["notional"],
        equity=10_000.0,
        entry_fee=o_btc["entry_fee"],
        candles=_hist_with_crash(),
        pipeline_payload=payload,
    )
    assert scen_btc["holding"]["financing_bps_per_day"] == 0.0
    assert scen_btc["holding"]["financing_eur_median"] == 0.0

    o_xau = _preview_like_outcomes(price=2000.0, notional=1000.0, stop_pct=0.01, tp_r=2.0, symbol="XAUUSD")
    scen_xau = build_scenarios(
        "XAUUSD",
        "1h",
        o_xau["entry_fill"],
        o_xau["qty"],
        o_xau["stop_price"],
        o_xau["take_profit_price"],
        o_xau["profile"],
        net_gain_if_target=o_xau["net_gain_if_target"],
        net_loss_if_stop=o_xau["net_loss_if_stop"],
        invested=o_xau["notional"],
        equity=10_000.0,
        entry_fee=o_xau["entry_fee"],
        candles=_hist_with_crash(),
        pipeline_payload=payload,
    )
    assert scen_xau["holding"]["financing_bps_per_day"] > 0
    assert scen_xau["holding"]["financing_eur_median"] > 0


def test_open_position_scenarios_align_with_liquidation():
    from app.paper.liquidation import preview_close_cash_delta

    profile = dict(BASELINE_PROFILE)
    pos = NS(
        id="p1",
        symbol="BTCUSDT",
        timeframe="1h",
        direction="LONG",
        qty=10.0,
        entry_price=100.0,
        notional=1000.0,
        entry_fee=0.5,
        stop_price=98.0,
        take_profit_price=104.0,
        entry_time=datetime(2026, 9, 20, tzinfo=timezone.utc),
        status="OPEN",
    )
    mark = 101.0
    scen = build_open_position_scenarios(
        pos,
        mark_price=mark,
        profile=profile,
        equity=10_000.0,
        financing_paid=0.0,
        candles=_hist_with_crash(),
        pipeline_payload=_fake_pipeline(n_trades=5),
    )
    expected = preview_close_cash_delta(pos, mark_price=mark, profile=profile)
    assert scen["liquidation_close_now"]["cash_delta"] == pytest.approx(expected["cash_delta"])
    assert scen["liquidation_close_now"]["net_eur_from_entry"] == pytest.approx(expected["realized"])
    assert scen["from_mark"]["crash"]["net_eur_from_entry"] <= scen["from_mark"]["stop"]["net_eur_from_entry"] + 1e-9


def test_causality_history_excludes_forming_bar_in_reference():
    # Append a forming bar with an even worse low — must be ignored.
    hist = _hist_with_crash() + [_candle(10_000_000_000, 50, 50, 1, 50)]
    o = _preview_like_outcomes(price=100.0, notional=1000.0, stop_pct=0.02, tp_r=2.0)
    scen = build_scenarios(
        o["symbol"],
        "1h",
        o["entry_fill"],
        o["qty"],
        o["stop_price"],
        o["take_profit_price"],
        o["profile"],
        net_gain_if_target=o["net_gain_if_target"],
        net_loss_if_stop=o["net_loss_if_stop"],
        invested=o["notional"],
        equity=10_000.0,
        entry_fee=o["entry_fee"],
        candles=hist,
        pipeline_payload=_fake_pipeline(n_trades=5),
    )
    assert scen["crash"]["reference"]["candle_time"] == 200
    assert scen["crash"]["reference"]["move"] == pytest.approx(-0.20)
