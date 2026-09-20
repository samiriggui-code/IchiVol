from datetime import datetime, timezone

from app.brokerage.execution import fill_at_quote, fill_candle_only, resolve_bar_exit
from app.market_data.binance_quotes import parse_book_ticker, parse_trades
from app.market_data.contracts import ExecutionMode, Provenance, Quote

T = datetime(2026, 9, 20, tzinfo=timezone.utc)
Q = Quote("X", bid=100.0, ask=100.5, bid_size=2.0, ask_size=1.0, provenance=Provenance("t", T, T))


def test_buy_at_ask_sell_at_bid():
    assert fill_at_quote("BUY", 0.5, Q).price == 100.5
    assert fill_at_quote("SELL", 0.5, Q).price == 100.0


def test_partial_when_size_exceeds_top_of_book():
    f = fill_at_quote("BUY", 3.0, Q)
    assert f.is_partial and f.filled_qty == 1.0 and f.reason == "partial_top_of_book"


def test_reject_when_partial_disallowed():
    f = fill_at_quote("BUY", 3.0, Q, allow_partial=False)
    assert f.rejected and f.price is None


def test_candle_only_is_adverse_and_labels_assumptions():
    b = fill_candle_only("BUY", 1, 100.0, half_spread_bps=5, slippage_bps=5)
    s = fill_candle_only("SELL", 1, 100.0, half_spread_bps=5, slippage_bps=5)
    assert b.price > 100 > s.price and b.model == ExecutionMode.CANDLE_ONLY
    assert "ASSUMPTION" in b.assumptions[0]


def test_seeded_jitter_reproducible():
    a = fill_candle_only("BUY", 1, 100.0, half_spread_bps=1, slippage_bps=1, jitter_bps=10, seed=42)
    b = fill_candle_only("BUY", 1, 100.0, half_spread_bps=1, slippage_bps=1, jitter_bps=10, seed=42)
    c = fill_candle_only("BUY", 1, 100.0, half_spread_bps=1, slippage_bps=1, jitter_bps=10, seed=43)
    assert a.price == b.price != c.price


def test_stop_and_target_same_bar_takes_stop():
    r = resolve_bar_exit("LONG", stop=95, target=110, bar_open=100, bar_high=111, bar_low=94)
    assert r.reason == "stop_hit" and r.price == 95 and "conservative" in r.note


def test_gap_beyond_stop_fills_at_open_not_stop():
    r = resolve_bar_exit("LONG", stop=95, target=110, bar_open=90, bar_high=92, bar_low=88)
    assert r.reason == "stop_gap" and r.price == 90
    s = resolve_bar_exit("SHORT", stop=105, target=90, bar_open=108, bar_high=109, bar_low=107)
    assert s.reason == "stop_gap" and s.price == 108


def test_no_exit_inside_range():
    assert resolve_bar_exit("LONG", 95, 110, 100, 105, 98).reason is None


def test_parse_binance_payloads_from_live_shape():
    q = parse_book_ticker("BTCUSDT", {"bidPrice": "80465.01", "bidQty": "7.88", "askPrice": "80465.02", "askQty": "0.002"}, T)
    assert q.spread > 0 and q.ask_size == 0.002 and q.provenance.delayed is None
    t = parse_trades("BTCUSDT", [{"price": "80470.03", "qty": "0.00008", "time": 1789905798329, "isBuyerMaker": True}], T)
    assert t[0].buyer_is_aggressor is False and t[0].provenance.market_time.tzinfo is not None
