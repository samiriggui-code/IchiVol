"""Trade CVD vs kline CVD — Lab microstructure (no network)."""

from __future__ import annotations

from app.indicators.cvd import CvdBias, CvdParams
from app.indicators.ichimoku import Candle
from app.microstructure.trade_cvd import (
    AggressorTrade,
    bucket_trade_deltas_to_bars,
    compare_kline_vs_trade_cvd,
    compute_trade_cvd,
    trade_delta,
)


def _c(t: int, vol: float, tb: float) -> Candle:
    return Candle(
        time=t,
        open=100.0,
        high=101.0,
        low=99.0,
        close=100.5,
        volume=vol,
        taker_buy_volume=tb,
    )


def test_trade_delta_sign():
    buy = AggressorTrade(time_ms=1000, price=1.0, size=2.5, buyer_is_aggressor=True)
    sell = AggressorTrade(time_ms=1000, price=1.0, size=2.5, buyer_is_aggressor=False)
    assert trade_delta(buy) == 2.5
    assert trade_delta(sell) == -2.5


def test_bucket_empty_bars_are_none():
    opens = [0, 60, 120]
    trades = [
        AggressorTrade(time_ms=10_000, price=1.0, size=1.0, buyer_is_aggressor=True),
        AggressorTrade(time_ms=70_000, price=1.0, size=2.0, buyer_is_aggressor=False),
    ]
    deltas = bucket_trade_deltas_to_bars(trades, opens, tf_seconds=60)
    assert deltas == [1.0, -2.0, None]


def test_trade_cvd_matches_kline_when_tape_equals_taker():
    # Bar delta kline = 2*tb - vol. Fabricate trades that sum to same delta.
    candles = [
        _c(0, vol=100.0, tb=80.0),  # delta +60
        _c(60, vol=100.0, tb=20.0),  # delta -60
    ]
    trades = [
        AggressorTrade(time_ms=1_000, price=1.0, size=80.0, buyer_is_aggressor=True),
        AggressorTrade(time_ms=2_000, price=1.0, size=20.0, buyer_is_aggressor=False),
        AggressorTrade(time_ms=61_000, price=1.0, size=20.0, buyer_is_aggressor=True),
        AggressorTrade(time_ms=62_000, price=1.0, size=80.0, buyer_is_aggressor=False),
    ]
    # net bar0: +80-20=+60; bar1: +20-80=-60
    states = compute_trade_cvd(candles, trades, tf_seconds=60, params=CvdParams(window=2))
    assert states[0].delta == 60.0
    assert states[1].delta == -60.0
    assert states[0].bias == CvdBias.BULLISH
    # Window [+60, -60] → rolling 0 → NEUTRAL (balanced pressure)
    assert states[1].bias == CvdBias.NEUTRAL


def test_compare_report_agreement():
    candles = [
        _c(0, vol=100.0, tb=80.0),
        _c(60, vol=100.0, tb=70.0),
        _c(120, vol=100.0, tb=30.0),
    ]
    trades = [
        AggressorTrade(time_ms=1_000, price=1.0, size=80.0, buyer_is_aggressor=True),
        AggressorTrade(time_ms=2_000, price=1.0, size=20.0, buyer_is_aggressor=False),
        AggressorTrade(time_ms=61_000, price=1.0, size=70.0, buyer_is_aggressor=True),
        AggressorTrade(time_ms=62_000, price=1.0, size=30.0, buyer_is_aggressor=False),
        AggressorTrade(time_ms=121_000, price=1.0, size=30.0, buyer_is_aggressor=True),
        AggressorTrade(time_ms=122_000, price=1.0, size=70.0, buyer_is_aggressor=False),
    ]
    report = compare_kline_vs_trade_cvd(
        candles,
        trades,
        symbol="BTCUSDT",
        timeframe="1m",
        tf_seconds=60,
        params=CvdParams(window=3, bias_threshold=0.05),
    )
    d = report.to_dict()
    assert d["symbol"] == "BTCUSDT"
    assert d["n_bars"] == 3
    assert d["n_trades"] == 6
    assert d["bars_with_trades"] == 3
    assert d["bias_agreement_rate"] == 1.0
    assert d["delta_corr"] is not None and d["delta_corr"] > 0.99
    assert "research only" in d["disclaimer"].lower()
    assert len(d["sample"]) >= 1
