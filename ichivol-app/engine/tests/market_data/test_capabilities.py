"""ProviderCapabilities — declarative inventory (V3 delta)."""

from __future__ import annotations

from app.market_data.capabilities import (
    get_capabilities,
    list_capabilities,
)
from app.market_data.registry import get_provider


def test_known_providers_have_capabilities():
    for pid in ("binance", "biquote", "twelve_data"):
        assert get_provider(pid) is not None
        caps = get_capabilities(pid)
        assert caps is not None
        assert caps.provider_id == pid
        assert caps.ohlcv is True


def test_binance_microstructure_flags():
    caps = get_capabilities("binance")
    assert caps is not None
    assert caps.real_volume is True
    assert caps.open_interest is True
    assert caps.funding is True
    assert caps.quotes is True
    assert caps.trades is True
    assert caps.depth is False
    assert caps.streaming is False


def test_biquote_tick_volume_no_exchange():
    caps = get_capabilities("biquote")
    assert caps is not None
    assert caps.tick_volume is True
    assert caps.real_volume is False
    assert caps.quotes is False


def test_list_capabilities_sorted():
    rows = list_capabilities()
    assert [c.provider_id for c in rows] == sorted(c.provider_id for c in rows)
    assert len(rows) == 3


def test_unknown_provider_none():
    assert get_capabilities("oanda") is None
    assert get_capabilities("ibkr") is None
