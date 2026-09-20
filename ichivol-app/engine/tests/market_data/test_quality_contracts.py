from datetime import datetime, timezone

import pytest

from app.indicators.ichimoku import Candle
from app.market_data.contracts import Provenance, Quote
from app.market_data.quality import closed_candles, validate_candles

H = 3600


def c(t, o=100, h=101, l=99, cl=100, v=1.0):
    return Candle(time=t, open=o, high=h, low=l, close=cl, volume=v)


def test_clean_series_ok():
    r = validate_candles([c(0), c(H), c(2 * H)], H)
    assert r.ok


def test_detects_gap_duplicate_order_ohlc_outlier():
    r = validate_candles([c(0), c(0), c(5 * H), c(4 * H), c(6 * H, h=90), c(7 * H, cl=200, h=200)], H)
    assert {"duplicate", "gap", "out_of_order", "ohlc_incoherent", "outlier_return"} <= r.codes()


def test_stale_and_incomplete_need_now():
    series = [c(0), c(H)]
    assert validate_candles(series, H).ok  # no `now` -> not guessed
    assert validate_candles(series, H, now=H + 10).has("incomplete_last_bar")
    assert validate_candles(series, H, now=2 * H + 10 * H).has("stale")


def test_closed_candles_drops_forming_bar():
    assert [x.time for x in closed_candles([c(0), c(H)], H, now=H + 10)] == [0]


def test_quote_rejects_crossed_and_keeps_provenance():
    t = datetime(2026, 9, 20, tzinfo=timezone.utc)
    p = Provenance(source="x", market_time=t, received_at=t)
    with pytest.raises(ValueError):
        Quote("BTCUSDT", bid=101, ask=100, provenance=p)
    q = Quote("BTCUSDT", bid=100, ask=101, provenance=p)
    assert q.spread == 1 and p.delayed is None
