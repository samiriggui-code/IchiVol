"""Mocked, deterministic coverage for app/market_data/binance.py's kline
parsing -- tests/market_data/test_binance.py hits the real API instead and
can't pin exact values.
"""

from __future__ import annotations

from app.market_data import binance


def _kline_row(taker_buy: str | None = "60.5") -> list:
    row = [
        1700000000000,  # open time (ms)
        "100.0", "101.0", "99.0", "100.5",  # OHLC
        "200.0",  # volume
        1700003600000,  # close time
        "20000.0",  # quote asset volume
        150,  # number of trades
    ]
    if taker_buy is not None:
        row.append(taker_buy)  # index 9: taker buy base asset volume
        row.append("12000.0")  # index 10: taker buy quote asset volume
        row.append("0")  # index 11: ignore
    return row


def test_fetch_klines_parses_taker_buy_volume(monkeypatch):
    class FakeResp:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> list:
            return [_kline_row("60.5")]

    monkeypatch.setattr(binance.httpx, "get", lambda *a, **k: FakeResp())
    candles = binance.fetch_klines("BTCUSDT", "1h", 1)
    assert candles[0].volume == 200.0
    assert candles[0].taker_buy_volume == 60.5


def test_fetch_klines_handles_a_short_row_without_taker_buy_volume(monkeypatch):
    # Defensive: a shorter/older row shape shouldn't crash the parse, just
    # leave CVD input as unavailable for that bar.
    class FakeResp:
        def raise_for_status(self) -> None:
            return None

        def json(self) -> list:
            return [_kline_row(None)]

    monkeypatch.setattr(binance.httpx, "get", lambda *a, **k: FakeResp())
    candles = binance.fetch_klines("BTCUSDT", "1h", 1)
    assert candles[0].taker_buy_volume is None
