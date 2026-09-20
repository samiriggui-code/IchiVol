from types import SimpleNamespace as R

from app.screener.cache import paper_tradable_rows


def test_crypto_forex_metals_indices_energy_are_tradable_but_not_jpy_or_equities():
    rows = [R(symbol=s, exchange=e) for s, e in [
        ("BTCUSDT", "binance"), ("EURUSD", "biquote"), ("XAUUSD", "biquote"), ("SPX", "biquote"),
        ("WTI", "biquote"), ("USDJPY", "biquote"), ("AAPL", "twelve_data"),
    ]]
    assert [r.symbol for r in paper_tradable_rows(rows)] == ["BTCUSDT", "EURUSD", "XAUUSD", "SPX", "WTI"]
