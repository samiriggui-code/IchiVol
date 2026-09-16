"""No network here -- resolve() only ever consults the catalog and the
provider registry; the actual HTTP fetch is exercised (with a real network
call) in test_binance.py and (mocked) in the screener/backtest tests.
"""

from __future__ import annotations

import pytest

from app.market_data import resolve as resolve_module
from app.market_data.resolve import ProviderNotWiredError, resolve, resolve_and_fetch
from app.universe.types import AssetClass, Instrument


def test_resolve_a_catalogued_wired_instrument():
    provider, provider_symbol = resolve("BTCUSDT")
    assert provider.id == "binance"
    assert provider_symbol == "BTCUSDT"


def test_resolve_ignores_default_provider_for_a_catalogued_instrument():
    # BTCUSDT's provider is fixed by the catalog regardless of what the
    # caller passes as a fallback default.
    provider, provider_symbol = resolve("BTCUSDT", default_provider="kraken")
    assert provider.id == "binance"
    assert provider_symbol == "BTCUSDT"


def test_resolve_raises_provider_not_wired_for_a_known_but_unwired_instrument(monkeypatch):
    # Every real catalog entry is wired now (crypto -> binance, equities ->
    # twelve_data, everything else -> biquote, see app/universe/catalog.py),
    # so this test injects its own bare placeholder rather than depending on
    # some business instrument happening to still be unwired -- resolve()'s
    # ProviderNotWiredError branch needs coverage independent of catalog
    # content.
    placeholder = Instrument(
        id="STILL_UNWIRED",
        asset_class=AssetClass.ENERGY,
        label="Still Unwired",
        provider=None,
        provider_symbol=None,
    )
    monkeypatch.setattr(
        resolve_module,
        "get_instrument",
        lambda symbol_or_id: placeholder if symbol_or_id == "STILL_UNWIRED" else None,
    )
    with pytest.raises(ProviderNotWiredError) as exc_info:
        resolve("STILL_UNWIRED")
    assert exc_info.value.instrument_id == "STILL_UNWIRED"
    assert exc_info.value.asset_class == "energy"
    assert "provider_not_wired" in str(exc_info.value)


def test_resolve_falls_back_to_default_provider_for_an_uncatalogued_symbol():
    provider, provider_symbol = resolve("SOME_TEST_FIXTURE_SYMBOL")
    assert provider.id == "binance"
    assert provider_symbol == "SOME_TEST_FIXTURE_SYMBOL"


def test_resolve_raises_value_error_for_an_uncatalogued_symbol_with_unknown_default():
    with pytest.raises(ValueError) as exc_info:
        resolve("SOME_TEST_FIXTURE_SYMBOL", default_provider="kraken")
    assert not isinstance(exc_info.value, ProviderNotWiredError)


def test_resolve_and_fetch_uses_the_plain_provider_call_for_binance(monkeypatch):
    # binance already serves the full requested depth in one call --
    # resolve_and_fetch must not route it through DB accumulation.
    from app.market_data import binance

    monkeypatch.setattr(binance, "fetch_klines", lambda symbol, tf, limit: ["plain-fetch-result"])
    provider, provider_symbol, candles = resolve_and_fetch("BTCUSDT", "1h", 300)
    assert provider.id == "binance"
    assert candles == ["plain-fetch-result"]


def test_resolve_and_fetch_routes_biquote_through_accumulation(monkeypatch):
    # Doesn't touch the DB or network -- just proves resolve_and_fetch
    # dispatches to app/market_data/accumulator.py for a provider that
    # needs_accumulation() flags, with the canonical `symbol` (not
    # `provider_symbol`) passed through for DB keying. Full accumulation
    # behavior itself is covered by tests/market_data/test_accumulator.py.
    placeholder = Instrument(
        id="FAKE_BIQUOTE",
        asset_class=AssetClass.FOREX,
        label="Fake",
        provider="biquote",
        provider_symbol="FAKESYM",
    )
    monkeypatch.setattr(
        resolve_module,
        "get_instrument",
        lambda symbol_or_id: placeholder if symbol_or_id == "FAKE_BIQUOTE" else None,
    )

    captured = {}

    def fake_fetch_with_accumulation(provider, symbol, provider_symbol, timeframe, limit):
        captured.update(
            provider_id=provider.id, symbol=symbol, provider_symbol=provider_symbol,
            timeframe=timeframe, limit=limit,
        )
        return ["accumulated-result"]

    monkeypatch.setattr(resolve_module, "fetch_with_accumulation", fake_fetch_with_accumulation)

    provider, provider_symbol, candles = resolve_and_fetch("FAKE_BIQUOTE", "1h", 500)

    assert candles == ["accumulated-result"]
    assert captured == {
        "provider_id": "biquote", "symbol": "FAKE_BIQUOTE", "provider_symbol": "FAKESYM",
        "timeframe": "1h", "limit": 500,
    }
