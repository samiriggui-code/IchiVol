from __future__ import annotations

from app.market_data.registry import get_provider


def test_get_provider_returns_binance():
    provider = get_provider("binance")
    assert provider is not None
    assert provider.id == "binance"
    assert hasattr(provider, "fetch_ohlcv")


def test_get_provider_returns_biquote():
    provider = get_provider("biquote")
    assert provider is not None
    assert provider.id == "biquote"
    assert hasattr(provider, "fetch_ohlcv")


def test_get_provider_returns_none_for_an_unregistered_id():
    assert get_provider("kraken") is None
    assert get_provider("oanda") is None


def test_get_provider_returns_none_for_mt5_when_disabled_by_default():
    # settings.mt5_enabled defaults to False -- MT5 must stay unregistered,
    # exactly like any other unwired id, unless an operator opts in via
    # MT5_ENABLED=true (docs/TRADING_ARCHITECTURE_V2.md §11: never a
    # dependency the engine needs to boot).
    assert get_provider("mt5") is None
