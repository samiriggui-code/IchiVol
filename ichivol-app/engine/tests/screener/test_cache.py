from __future__ import annotations

import time

from app.screener import cache as cache_module
from app.screener.cache import ScreenerCache
from app.screener.service import ScreenerRow


def _fake_scan_watchlist(symbols, timeframe="1h", limit=300):
    return [
        ScreenerRow(
            symbol=s,
            exchange="binance",
            timeframe=timeframe,
            price=1.0,
            candles=[],
            ichimoku=None,
            rvol=None,
            decision=None,
            pipeline=None,
        )
        for s in symbols[:1]
    ]


def test_get_returns_none_before_first_refresh():
    c = ScreenerCache(refresh_interval_s=999)
    assert c.get() is None


def test_refresh_populates_the_cache_without_persisting(monkeypatch):
    monkeypatch.setattr(cache_module, "scan_watchlist", _fake_scan_watchlist)
    c = ScreenerCache(refresh_interval_s=999, default_timeframe="1h")

    entry = c.refresh(persist=False)
    assert entry.timeframe == "1h"
    assert len(entry.rows) == 1

    fetched = c.get()
    assert fetched is entry


def test_get_ignores_a_stale_timeframe(monkeypatch):
    monkeypatch.setattr(cache_module, "scan_watchlist", _fake_scan_watchlist)
    c = ScreenerCache(refresh_interval_s=999, default_timeframe="1h")
    c.refresh(timeframe="1h", persist=False)

    assert c.get(timeframe="4h") is None
    assert c.get(timeframe="1h") is not None


def test_background_thread_refreshes_at_least_once(monkeypatch):
    monkeypatch.setattr(cache_module, "scan_watchlist", _fake_scan_watchlist)
    # Isolate this test from real DB timing/availability -- persistence
    # itself is covered by test_refresh_survives_a_persist_failure below.
    monkeypatch.setattr(cache_module, "persist_scan", lambda session, row: None)

    c = ScreenerCache(refresh_interval_s=0.05, default_timeframe="1h")
    try:
        c.start()
        deadline = time.time() + 2.0
        while c.get() is None and time.time() < deadline:
            time.sleep(0.02)
        assert c.get() is not None, "background thread never populated the cache"
    finally:
        c.stop()


def test_refresh_only_feeds_crypto_rows_to_paper_trading(monkeypatch):
    # Crypto-only for now (docs/HANDOFF-CLAUDE-CDC-CAP-2026-09-16.md §1.5:
    # "Paper/watch multi-classe = après paper crypto stable (V2)").
    from app.paper import engine as paper_engine

    def _mixed_watchlist(symbols, timeframe="1h", limit=300):
        return [
            ScreenerRow(
                symbol="BTCUSDT", exchange="binance", timeframe=timeframe, price=1.0,
                candles=[], ichimoku=None, rvol=None, decision=None, pipeline=None,
            ),
            ScreenerRow(
                symbol="EURUSD", exchange="biquote", timeframe=timeframe, price=1.0,
                candles=[], ichimoku=None, rvol=None, decision=None, pipeline=None,
            ),
        ]

    captured = {}
    monkeypatch.setattr(cache_module, "scan_watchlist", _mixed_watchlist)
    monkeypatch.setattr(cache_module, "persist_scan", lambda session, row: None)
    monkeypatch.setattr(
        paper_engine, "sync_auto_watchlist",
        lambda session, rows: captured.setdefault("rows", rows) and []
    )

    c = ScreenerCache(refresh_interval_s=999)
    c.refresh(persist=True)

    assert [r.symbol for r in captured["rows"]] == ["BTCUSDT"]


def test_refresh_survives_a_persist_failure(monkeypatch):
    def boom(session, row):
        raise RuntimeError("simulated DB failure")

    monkeypatch.setattr(cache_module, "scan_watchlist", _fake_scan_watchlist)
    monkeypatch.setattr(cache_module, "persist_scan", boom)

    class FakeSession:
        def rollback(self):
            pass

        def close(self):
            pass

    monkeypatch.setattr(cache_module, "SessionLocal", lambda: FakeSession())

    c = ScreenerCache(refresh_interval_s=999)
    entry = c.refresh(persist=True)  # must not raise despite persist_scan blowing up
    assert len(entry.rows) == 1
