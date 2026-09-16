from __future__ import annotations

from app.universe.catalog import (
    UNIVERSE,
    by_class,
    default_watchlist,
    get_instrument,
    wired_instruments,
)
from app.universe.types import AssetClass


def test_get_instrument_finds_a_known_id():
    btc = get_instrument("BTCUSDT")
    assert btc is not None
    assert btc.asset_class == AssetClass.CRYPTO
    assert btc.provider == "binance"
    assert btc.provider_symbol == "BTCUSDT"
    assert btc.is_wired is True


def test_get_instrument_returns_none_for_an_unknown_id():
    assert get_instrument("NOT_A_REAL_INSTRUMENT") is None


def test_every_asset_class_has_at_least_one_instrument():
    for asset_class in AssetClass:
        instruments = by_class(asset_class)
        assert instruments, f"no instruments registered for {asset_class}"


def test_crypto_wired_via_binance_equity_via_twelve_data_rest_via_biquote():
    wired = wired_instruments()
    assert wired
    by_provider = {i.provider for i in wired}
    assert by_provider == {"binance", "twelve_data", "biquote"}

    aapl = get_instrument("AAPL")
    assert aapl is not None
    assert aapl.provider == "twelve_data"
    assert aapl.provider_symbol == "AAPL"

    eurusd = get_instrument("EURUSD")
    assert eurusd is not None
    assert eurusd.provider == "biquote"
    assert eurusd.provider_symbol == "EURUSD"
    assert eurusd.is_wired is True

    xau = get_instrument("XAUUSD")
    assert xau is not None
    assert xau.provider == "biquote"
    assert xau.provider_symbol == "XAUUSD"


def test_energy_and_index_now_wired_via_biquote():
    wti = get_instrument("WTI")
    assert wti is not None
    assert wti.provider == "biquote"
    assert wti.provider_symbol == "USOIL"  # "WTI" ticker itself has no data
    assert wti.is_wired is True

    spx = get_instrument("SPX")
    assert spx is not None
    assert spx.provider == "biquote"
    assert spx.provider_symbol == "US500"  # "SPX500" ticker has no data
    assert spx.is_wired is True


def test_default_watchlist_is_crypto_plus_biquote_not_twelve_data():
    watchlist = default_watchlist()
    expected = {
        i.id
        for i in wired_instruments()
        if i.enabled and i.provider in ("binance", "biquote")
    }
    assert set(watchlist) == expected
    assert "EURUSD" in watchlist
    assert "XAUUSD" in watchlist
    assert "AAPL" not in watchlist


def test_instrument_ids_are_unique():
    ids = [i.id for i in UNIVERSE]
    assert len(ids) == len(set(ids))
