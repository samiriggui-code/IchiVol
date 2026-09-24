"""Trade VP vs kline VP — Lab microstructure (no network)."""

from __future__ import annotations

from app.indicators.ichimoku import Candle
from app.microstructure.trade_cvd import AggressorTrade
from app.microstructure.trade_vp import (
    TradeVpParams,
    compare_kline_vs_trade_vp,
    compute_kline_volume_profile,
    compute_trade_volume_profile,
)


def test_trade_vp_poc_near_dense_price():
    trades = [
        AggressorTrade(1, 100.0, 1.0, True),
        AggressorTrade(2, 100.1, 1.0, True),
        AggressorTrade(3, 110.0, 10.0, True),
        AggressorTrade(4, 110.05, 10.0, False),
        AggressorTrade(5, 110.1, 10.0, True),
        AggressorTrade(6, 90.0, 1.0, False),
    ]
    levels = compute_trade_volume_profile(trades, TradeVpParams(num_bins=20))
    assert levels.poc is not None
    assert 108.0 <= levels.poc <= 112.0
    assert levels.vah is not None and levels.val is not None
    assert levels.val <= levels.poc <= levels.vah


def test_kline_vp_basic():
    candles = [
        Candle(time=i, open=100, high=101, low=99, close=100.5, volume=10.0)
        for i in range(5)
    ]
    candles.append(
        Candle(time=5, open=110, high=111, low=109, close=110.5, volume=100.0)
    )
    levels = compute_kline_volume_profile(candles, TradeVpParams(num_bins=12))
    assert levels.poc is not None
    assert levels.poc > 105.0


def test_compare_report():
    candles = [
        Candle(time=0, open=100, high=101, low=99, close=100, volume=50.0),
        Candle(time=60, open=100, high=102, low=99, close=101, volume=50.0),
    ]
    trades = [
        AggressorTrade(1000, 100.0, 25.0, True),
        AggressorTrade(2000, 100.5, 25.0, False),
        AggressorTrade(61_000, 101.0, 30.0, True),
        AggressorTrade(62_000, 101.5, 20.0, False),
    ]
    report = compare_kline_vs_trade_vp(
        candles, trades, symbol="BTCUSDT", timeframe="1h"
    )
    d = report.to_dict()
    assert d["symbol"] == "BTCUSDT"
    assert d["n_trades"] == 4
    assert d["trade"]["poc"] is not None
    assert "research only" in d["disclaimer"].lower()
