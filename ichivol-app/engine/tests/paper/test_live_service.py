"""Service Binance en direct : symboles crypto du compte unique, contrôleur unique (verrou PostgreSQL)."""

from __future__ import annotations

import pytest
from sqlalchemy.exc import OperationalError

from app.db.session import engine
from app.paper.live_service import LiveMarketService, _Leadership, live_crypto_symbols
from app.paper.strategy_profiles import MAIN_PROFILE


def test_live_symbols_are_the_spot_crypto_of_the_main_universe():
    syms = live_crypto_symbols()
    assert "BTCUSDT" in syms and syms["BTCUSDT"] == "BTCUSDT"
    assert "TRXUSDT" in syms  # paire élargie hors catalogue : même symbole sur Binance
    for cfd in ("EURUSD", "XAUUSD", "SPX", "YM"):
        assert cfd not in syms  # CFD et futures restent en REST
    assert set(syms) <= set(MAIN_PROFILE["universe_symbols"])


def test_status_when_disabled():
    st = LiveMarketService().status()
    assert st["enabled"] is False and st["role"] == "disabled" and st["feed"]["state"] == "inactive"


def test_configured_service_exposes_feed_and_protection_status():
    svc = LiveMarketService()
    svc.configure(ws_base="wss://example.invalid", rest_base="https://example.invalid", stale_after_s=10,
                  rest_poll_s=5, refresh_s=5)
    st = svc.status()
    assert st["feed"]["symbols"] == len(live_crypto_symbols())
    assert st["feed"]["state"] == "degraded" and st["feed"]["connected"] is False
    assert st["protection"]["watched_lots"] == 0


try:
    with engine.connect() as _c:
        DB = _c.dialect.name == "postgresql"
except OperationalError:
    DB = False


@pytest.mark.skipif(not DB, reason="PostgreSQL not reachable")
def test_only_one_controller_holds_the_advisory_lock():
    a, b = _Leadership(), _Leadership()
    try:
        assert a.try_acquire() is True
        assert b.try_acquire() is False  # second worker / conteneur : en attente
        a.release()
        assert b.try_acquire() is True  # le verrou se libère avec le contrôleur
    finally:
        a.release()
        b.release()
