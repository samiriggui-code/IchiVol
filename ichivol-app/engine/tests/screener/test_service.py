from __future__ import annotations

import pytest

from app.agents.types import Direction
from app.indicators.ichimoku import Candle
from app.market_data import binance, binance_futures
from app.market_data.resolve import ProviderNotWiredError
from app.screener import service


@pytest.fixture(autouse=True)
def _no_live_oi_funding_calls(monkeypatch):
    # scan_symbol() now also fetches Open Interest + Funding Rate for
    # Binance-backed symbols (app/indicators/oi_funding.py, V2) -- these
    # tests only mock OHLCV (binance.fetch_klines) and must stay
    # network-free, so stub the futures endpoints to "no data" (the same
    # graceful-degradation path a real network failure takes).
    monkeypatch.setattr(binance_futures, "fetch_open_interest_hist", lambda *a, **k: [])
    monkeypatch.setattr(binance_futures, "fetch_funding_rate_hist", lambda *a, **k: [])


def _uptrend_with_spike(n: int) -> list[Candle]:
    volumes = [50.0] * (n - 1) + [250.0]
    return [
        Candle(
            time=i, open=100 + i, high=101 + i, low=99 + i, close=100.5 + i, volume=volumes[i]
        )
        for i in range(n)
    ]


def _flat(n: int) -> list[Candle]:
    return [Candle(time=i, open=50, high=50, low=50, close=50, volume=200.0) for i in range(n)]


def test_scan_symbol_combines_agents_into_a_decision(monkeypatch):
    candles = _uptrend_with_spike(160)
    monkeypatch.setattr(binance, "fetch_klines", lambda symbol, tf, limit: candles)

    row = service.scan_symbol("BTCUSDT", timeframe="1h", limit=160)

    assert row.symbol == "BTCUSDT"
    assert row.exchange == "binance"
    assert row.price == candles[-1].close
    assert row.decision.direction == Direction.LONG
    assert row.decision.decision == "STRONG_BUY"
    # Raw ATR state surfaced on the row (not just embedded in the Régime
    # stage's prose summary) -- see docs/HANDOFF-CURSOR-PIPELINE-NATIVE.md
    # §14: a caller acting on the decision needs a numeric stop distance.
    assert row.atr is not None
    assert row.atr.suggested_stop_distance is not None
    assert row.atr.suggested_stop_distance > 0


def test_scan_symbol_rejects_unsupported_exchange_for_an_uncatalogued_symbol(monkeypatch):
    # "TESTUSDT" isn't a catalog instrument, so resolution falls back to the
    # `exchange` param -- which "kraken" doesn't satisfy (only binance is
    # registered). A *catalogued* symbol like "BTCUSDT" would ignore this
    # param entirely and resolve to its fixed binance provider regardless
    # (see test_catalogued_symbol_ignores_the_exchange_param_below).
    monkeypatch.setattr(binance, "fetch_klines", lambda symbol, tf, limit: _flat(5))
    with pytest.raises(ValueError):
        service.scan_symbol("TESTUSDT", exchange="kraken")


def test_catalogued_symbol_ignores_the_exchange_param(monkeypatch):
    candles = _uptrend_with_spike(160)
    monkeypatch.setattr(binance, "fetch_klines", lambda symbol, tf, limit: candles)

    # BTCUSDT's provider is fixed by the catalog (binance) -- an unrelated
    # `exchange` override for an already-catalogued instrument doesn't
    # change that (unlike an uncatalogued symbol, which uses it as a
    # fallback default).
    row = service.scan_symbol("BTCUSDT", exchange="kraken", timeframe="1h", limit=160)
    assert row.exchange == "binance"


def test_scan_symbol_raises_provider_not_wired_for_a_known_unwired_instrument(monkeypatch):
    # Every real catalog entry is wired now (crypto -> binance, equities ->
    # twelve_data, everything else -> biquote, see app/universe/catalog.py),
    # so this injects its own bare placeholder rather than depending on some
    # business instrument happening to still be unwired -- same approach as
    # tests/market_data/test_resolve.py.
    import app.market_data.resolve as resolve_module
    from app.universe.types import AssetClass, Instrument

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
    with pytest.raises(ProviderNotWiredError):
        service.scan_symbol("STILL_UNWIRED")


def test_scan_symbol_rejects_too_little_history(monkeypatch):
    monkeypatch.setattr(binance, "fetch_klines", lambda symbol, tf, limit: _flat(1))
    with pytest.raises(ValueError):
        service.scan_symbol("BTCUSDT")


def test_scan_watchlist_ranks_actionable_decisions_first(monkeypatch):
    per_symbol = {
        "AAA": _flat(160),  # neutral -> WAIT
        "BBB": _uptrend_with_spike(160),  # LONG, confirmed by volume -> STRONG_BUY
    }
    monkeypatch.setattr(
        binance, "fetch_klines", lambda symbol, tf, limit: per_symbol[symbol]
    )

    rows = service.scan_watchlist(symbols=["AAA", "BBB"])

    assert [r.symbol for r in rows] == ["BBB", "AAA"]


def test_scan_watchlist_skips_a_failing_symbol_without_raising(monkeypatch):
    def fake_fetch(symbol, tf, limit):
        if symbol == "BROKEN":
            raise RuntimeError("simulated network failure")
        return _uptrend_with_spike(160)

    monkeypatch.setattr(binance, "fetch_klines", fake_fetch)

    rows = service.scan_watchlist(symbols=["BROKEN", "BTCUSDT"])

    assert [r.symbol for r in rows] == ["BTCUSDT"]


def test_scan_watchlist_threads_custom_rvol_params_through_to_each_symbol(monkeypatch):
    # Last bar's volume spike (250 vs a ~60 trailing average) clears the
    # default anomaly_threshold (3.0) -> ANOMALY. Raising anomaly_threshold
    # well above the observed RVOL demotes it to STRONG without touching
    # the fixture -- proof the override actually reaches scan_symbol's
    # RVOL_AGENT call, not just accepted and dropped.
    from app.indicators.rvol import RvolParams

    candles = _uptrend_with_spike(160)
    monkeypatch.setattr(binance, "fetch_klines", lambda symbol, tf, limit: candles)

    default_rows = service.scan_watchlist(symbols=["BTCUSDT"])
    assert default_rows[0].rvol.metadata["anomaly_level"] == "ANOMALY"

    custom_rows = service.scan_watchlist(
        symbols=["BTCUSDT"], rvol_params=RvolParams(anomaly_threshold=100.0)
    )
    assert custom_rows[0].rvol.metadata["anomaly_level"] == "STRONG"


def test_scan_symbol_wires_oi_and_funding_for_a_binance_symbol(monkeypatch):
    from app.market_data.binance_futures import FundingPoint, OpenInterestPoint

    candles = _uptrend_with_spike(160)
    monkeypatch.setattr(binance, "fetch_klines", lambda symbol, tf, limit: candles)
    monkeypatch.setattr(
        binance_futures, "fetch_open_interest_hist",
        lambda symbol, period, limit=500: [
            OpenInterestPoint(time=i, open_interest=1000.0 * (1.01**i)) for i in range(160)
        ],
    )
    monkeypatch.setattr(
        binance_futures, "fetch_funding_rate_hist",
        lambda symbol, limit=200: [FundingPoint(time=0, rate=0.001)],
    )

    row = service.scan_symbol("BTCUSDT", timeframe="1h", limit=160)
    participation = next(s for s in row.pipeline.stages if s.id.value == "participation")
    assert "oi_rising" in participation.codes
    assert "funding_crowded_long" in participation.codes


def test_scan_symbol_skips_oi_funding_for_a_non_binance_provider(monkeypatch):
    # biquote/twelve_data-backed instruments have no futures/OI/funding
    # concept -- must never even attempt the fetch. Faking resolve_and_fetch
    # itself keeps this test about the provider-id gate, not about any
    # specific non-binance provider's own fetch mechanics.
    called = []
    monkeypatch.setattr(
        binance_futures, "fetch_open_interest_hist",
        lambda *a, **k: called.append("oi") or []
    )

    class _FakeProvider:
        id = "twelve_data"

    candles = _uptrend_with_spike(160)
    monkeypatch.setattr(
        service, "resolve_and_fetch",
        lambda symbol, timeframe, limit, default_provider="binance": (_FakeProvider(), symbol, candles),
    )
    service.scan_symbol("EURUSD", timeframe="1h", limit=160)
    assert called == []


def test_default_watchlist_matches_the_catalogs_wired_crypto_and_biquote_instruments():
    from app.universe.catalog import default_watchlist

    assert list(service.DEFAULT_WATCHLIST) == default_watchlist()
    assert "BTCUSDT" in service.DEFAULT_WATCHLIST
    # biquote (Phase 1c, free/keyless) has no scarce budget to protect, so
    # it's in the default watchlist alongside crypto -- unlike the
    # Twelve Data-backed equities, kept out to protect its free-tier quota.
    assert "EURUSD" in service.DEFAULT_WATCHLIST
    assert "AAPL" not in service.DEFAULT_WATCHLIST
