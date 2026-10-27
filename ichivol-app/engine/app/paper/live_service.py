"""Service « Binance en direct » du moteur : flux bookTicker + stops / objectifs temps réel du compte unique.

Où ça tourne : un thread du processus engine (comme ``protection_monitor`` et ``screener_cache``), démarré par
``app/main.py`` quand ``ENABLE_LIVE_FEED=true``. Un seul contrôleur à la fois : avant de se connecter, le service
prend un verrou consultatif PostgreSQL (``pg_try_advisory_lock``) sur une connexion dédiée, gardée ouverte. Un
second worker uvicorn, un second conteneur ou un redémarrage qui chevauche l'ancien processus reste « en
attente » (``standby``) et réessaie toutes les 30 s ; le verrou se libère tout seul si le processus meurt. Même
sans ce verrou, une double clôture est impossible (relecture du lot sous le verrou du compte), mais on évite deux
connexions et des tentatives inutiles.

Symboles : les paires crypto de ``MAIN_PROFILE["universe_symbols"]`` (CFD et futures restent en REST / Twelve
Data / biquote, hors périmètre).
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
from typing import Any

from app.market_data.binance_live import BinanceLiveFeed, LivePriceCache
from app.paper.live_protection import LiveProtector

logger = logging.getLogger(__name__)

ADVISORY_LOCK_KEY = 0x1C41_B1AE  # « IchiVol Binance live » : clé fixe, propre à ce service
LEADER_RETRY_S = 30.0


def live_crypto_symbols(profile: dict[str, Any] | None = None) -> dict[str, str]:
    """{symbole du compte: symbole du flux Binance} des paires crypto au comptant de l'univers du compte unique."""
    from app.paper.strategy_profiles import MAIN_PROFILE, _is_spot_crypto
    from app.universe.catalog import get_instrument

    prof = MAIN_PROFILE if profile is None else profile
    out: dict[str, str] = {}
    for sym in prof.get("universe_symbols") or []:
        if not _is_spot_crypto(sym):
            continue
        inst = get_instrument(sym)
        if inst is not None and inst.provider != "binance":
            continue
        out[sym] = (inst.provider_symbol if inst is not None and inst.provider_symbol else sym).upper()
    return out


class _Leadership:
    """Verrou consultatif PostgreSQL tenu par une connexion dédiée (aucun verrou hors PostgreSQL)."""

    def __init__(self) -> None:
        self._conn: Any = None

    def try_acquire(self) -> bool:
        from sqlalchemy import text

        from app.db.session import engine

        if engine.dialect.name != "postgresql":
            return True
        conn = engine.connect()
        try:
            got = bool(conn.execute(text("SELECT pg_try_advisory_lock(:k)"), {"k": ADVISORY_LOCK_KEY}).scalar())
        except Exception:
            conn.close()
            raise
        if not got:
            conn.close()
            return False
        conn.commit()  # la session garde le verrou ; on ne laisse pas de transaction ouverte
        self._conn = conn
        return True

    def release(self) -> None:
        if self._conn is None:
            return
        try:
            from sqlalchemy import text

            self._conn.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": ADVISORY_LOCK_KEY})
            self._conn.commit()
        except Exception:  # la fermeture de la connexion libère le verrou de toute façon
            logger.debug("binance live: unlock failed", exc_info=True)
        finally:
            self._conn.close()
            self._conn = None


class LiveMarketService:
    def __init__(self) -> None:
        self.enabled = False
        self.role = "disabled"  # disabled | standby | leader | stopped
        self.cache = LivePriceCache()
        self.feed: BinanceLiveFeed | None = None
        self.protector: LiveProtector | None = None
        self.symbol_map: dict[str, str] = {}
        self._thread: threading.Thread | None = None
        self._stop_evt = threading.Event()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._async_stop: asyncio.Event | None = None
        self._leader = _Leadership()
        self.last_error: str | None = None

    def configure(self, *, ws_base: str, rest_base: str, stale_after_s: float, rest_poll_s: float, refresh_s: float) -> None:
        from app.paper.strategy_profiles import MAIN_CODE

        self.symbol_map = live_crypto_symbols()
        self.protector = LiveProtector(
            self.cache, symbol_map=self.symbol_map, portfolio_code=MAIN_CODE, refresh_s=refresh_s,
        )
        self.feed = BinanceLiveFeed(
            symbols=list(self.symbol_map.values()), cache=self.cache, ws_base=ws_base, rest_base=rest_base,
            stale_after_s=stale_after_s, rest_poll_s=rest_poll_s, on_quote=self.protector.on_quote,
        )

    def start(self) -> None:
        if self._thread is not None:
            return
        if self.feed is None:
            from app.config import settings

            self.configure(
                ws_base=settings.live_feed_ws_base, rest_base=settings.live_feed_rest_base,
                stale_after_s=settings.live_feed_stale_s, rest_poll_s=settings.live_feed_rest_poll_s,
                refresh_s=settings.live_feed_refresh_s,
            )
        self.enabled = True
        self.role = "standby"
        self._stop_evt.clear()
        self._thread = threading.Thread(target=self._run, daemon=True, name="binance-live")
        self._thread.start()

    def stop(self) -> None:
        self._stop_evt.set()
        if self._loop is not None and self._async_stop is not None:
            self._loop.call_soon_threadsafe(self._async_stop.set)
        if self.protector is not None:
            self.protector.stop()

    def _run(self) -> None:
        while not self._stop_evt.is_set():
            try:
                if self._leader.try_acquire():
                    break
            except Exception as exc:  # noqa: BLE001 -- base injoignable : on réessaie
                self.last_error = f"leadership: {type(exc).__name__}: {exc}"[:200]
            self.role = "standby"
            self._stop_evt.wait(LEADER_RETRY_S)
        if self._stop_evt.is_set():
            self.role = "stopped"
            return
        self.role = "leader"
        logger.info("binance live: contrôleur actif, %d symboles", len(self.symbol_map))
        assert self.feed is not None and self.protector is not None
        self.protector.start()
        try:
            asyncio.run(self._main())
        except Exception as exc:
            self.last_error = f"{type(exc).__name__}: {exc}"[:200]
            logger.warning("binance live: boucle arrêtée", exc_info=True)
        finally:
            self.protector.stop()
            self._leader.release()
            self.role = "stopped"

    async def _main(self) -> None:
        assert self.feed is not None
        self._loop = asyncio.get_running_loop()
        self._async_stop = asyncio.Event()
        if self._stop_evt.is_set():
            return
        await asyncio.gather(self.feed.run(self._async_stop), self.feed.rest_fallback_loop(self._async_stop))

    def status(self) -> dict[str, Any]:
        out: dict[str, Any] = {"enabled": self.enabled, "role": self.role, "last_error": self.last_error}
        if self.feed is not None:
            out["feed"] = self.feed.status()
        else:
            out["feed"] = {"state": "inactive", "symbols": 0}
        if self.protector is not None:
            out["protection"] = self.protector.status()
        out["checked_at_ms"] = int(time.time() * 1000)
        return out


live_market_service = LiveMarketService()
