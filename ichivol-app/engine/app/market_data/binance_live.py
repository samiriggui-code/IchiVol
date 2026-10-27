"""Flux direct Binance (WebSocket public, données de marché seulement) : meilleur bid / ask en mémoire.

Aucun compte, aucune clé, aucun ordre : ``wss://data-stream.binance.vision`` (le même hôte que le collecteur de
carnet, ``app/microstructure/book/collector.py``) sert uniquement les flux publics.

- Flux combinés ``<symbole>@bookTicker`` : meilleur bid / ask à chaque changement (pas d'horodatage de place sur
  le spot : l'heure de réception fait foi, comme ``binance_quotes.parse_book_ticker``).
- Reconnexion avec backoff (1 s doublé jusqu'à 30 s), ping / pong gérés par ``websockets`` (ping toutes les
  20 s ; les pings de Binance reçoivent leur pong automatiquement), reconnexion planifiée avant les 24 h.
- Flux figé : aucun message depuis ``stale_after_s`` → état « dégradé », la connexion est fermée et rouverte ;
  pendant ce temps le service interroge le REST ``/api/v3/ticker/bookTicker`` (retour automatique au REST).
- Dernier prix gardé en mémoire avec son horodatage (``LivePriceCache``), lu par la surveillance des stops
  (``app/paper/live_protection.py``) et par la route de santé.

Rien ici ne décide d'un trade : ce module ne fait que tenir des prix.
"""

from __future__ import annotations

import asyncio
import json
import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

DEFAULT_WS_BASE = "wss://data-stream.binance.vision"
DEFAULT_REST_BASE = "https://data-api.binance.vision"
PLANNED_RECONNECT_S = 23 * 3600  # Binance ferme les WebSocket au bout de 24 h
MAX_BACKOFF_S = 30.0


def now_ms() -> int:
    return int(time.time() * 1000)


@dataclass(frozen=True)
class LiveQuote:
    """Meilleur bid / ask d'un symbole, reçu à ``received_ms`` (horloge locale, ms)."""

    symbol: str
    bid: float
    ask: float
    received_ms: int
    bid_qty: float | None = None
    ask_qty: float | None = None
    source: str = "ws"  # ws | rest
    update_id: int | None = None

    @property
    def mid(self) -> float:
        return (self.bid + self.ask) / 2.0

    def age_ms(self, at_ms: int | None = None) -> int:
        return max(0, (now_ms() if at_ms is None else at_ms) - self.received_ms)


def parse_book_ticker_message(text: str, received_ms: int) -> LiveQuote | None:
    """Message du flux combiné (``{"stream": ..., "data": {...}}``) ou brut → ``LiveQuote``.

    Renvoie None pour tout ce qui n'est pas un bookTicker exploitable (réponse d'abonnement, prix nuls,
    carnet croisé) : un prix faux ne doit jamais entrer dans le cache."""
    try:
        msg = json.loads(text)
    except (TypeError, ValueError):
        return None
    if not isinstance(msg, dict):
        return None
    data = msg.get("data", msg)
    if not isinstance(data, dict) or "s" not in data or "b" not in data or "a" not in data:
        return None
    try:
        bid, ask = float(data["b"]), float(data["a"])
        bid_qty = float(data["B"]) if "B" in data else None
        ask_qty = float(data["A"]) if "A" in data else None
    except (TypeError, ValueError):
        return None
    if not (bid > 0 and ask > 0) or ask < bid:
        return None
    uid = data.get("u")
    return LiveQuote(
        symbol=str(data["s"]).upper(), bid=bid, ask=ask, received_ms=received_ms,
        bid_qty=bid_qty, ask_qty=ask_qty, source="ws", update_id=int(uid) if uid is not None else None,
    )


def parse_rest_book_tickers(rows: Any, received_ms: int) -> list[LiveQuote]:
    """Réponse REST ``/api/v3/ticker/bookTicker`` (liste ou objet) → quotes valides."""
    out: list[LiveQuote] = []
    for r in rows if isinstance(rows, list) else [rows]:
        try:
            bid, ask = float(r["bidPrice"]), float(r["askPrice"])
        except (KeyError, TypeError, ValueError):
            continue
        if bid > 0 and ask >= bid:
            out.append(LiveQuote(
                symbol=str(r["symbol"]).upper(), bid=bid, ask=ask, received_ms=received_ms,
                bid_qty=float(r.get("bidQty") or 0) or None, ask_qty=float(r.get("askQty") or 0) or None,
                source="rest",
            ))
    return out


class LivePriceCache:
    """Dernier bid / ask par symbole, partagé entre threads (le flux écrit, les lecteurs copient)."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._quotes: dict[str, LiveQuote] = {}

    def put(self, q: LiveQuote) -> None:
        with self._lock:
            cur = self._quotes.get(q.symbol)
            # Un relevé REST plus ancien que le dernier message WS ne l'écrase pas.
            if cur is not None and cur.received_ms > q.received_ms:
                return
            self._quotes[q.symbol] = q

    def get(self, symbol: str, *, max_age_ms: int | None = None, at_ms: int | None = None) -> LiveQuote | None:
        with self._lock:
            q = self._quotes.get(symbol.upper())
        if q is None:
            return None
        if max_age_ms is not None and q.age_ms(at_ms) > max_age_ms:
            return None
        return q

    def snapshot(self) -> dict[str, LiveQuote]:
        with self._lock:
            return dict(self._quotes)

    def clear(self) -> None:
        with self._lock:
            self._quotes.clear()


# Fabrique de connexion injectable (tests : faux WebSocket, aucun réseau).
ConnectFn = Callable[[str], Any]


@dataclass
class FeedStats:
    connected: bool = False
    connected_since_ms: int | None = None
    last_message_ms: int | None = None
    messages: int = 0
    reconnects: int = 0
    stale_events: int = 0
    rest_polls: int = 0
    rest_errors: int = 0
    last_rest_ms: int | None = None
    last_error: str | None = None


def _default_connect(url: str) -> Any:
    from websockets.asyncio.client import connect

    return connect(url, open_timeout=15, ping_interval=20, ping_timeout=20, max_size=2**20)


@dataclass
class BinanceLiveFeed:
    """Connexion WebSocket bookTicker multi-symboles, sans logique de trading.

    ``on_quote`` est appelé dans la boucle asyncio pour chaque prix valide (WS ou REST) : il doit rester
    rapide (la surveillance des stops ne fait qu'une comparaison en mémoire et délègue la clôture)."""

    symbols: list[str]
    cache: LivePriceCache = field(default_factory=LivePriceCache)
    ws_base: str = DEFAULT_WS_BASE
    rest_base: str = DEFAULT_REST_BASE
    stale_after_s: float = 10.0
    rest_poll_s: float = 5.0
    on_quote: Callable[[LiveQuote], None] | None = None
    connect: ConnectFn = _default_connect
    rest_fetch: Callable[[list[str]], Any] | None = None
    clock_ms: Callable[[], int] = now_ms
    stats: FeedStats = field(default_factory=FeedStats)

    def __post_init__(self) -> None:
        self.symbols = sorted({s.upper() for s in self.symbols if s})

    @property
    def stream_url(self) -> str:
        streams = "/".join(f"{s.lower()}@bookTicker" for s in self.symbols)
        return f"{self.ws_base}/stream?streams={streams}"

    # --- état ---------------------------------------------------------------------------------------

    def is_live(self) -> bool:
        """Connecté ET un message reçu depuis moins de ``stale_after_s``."""
        st = self.stats
        if not st.connected or st.last_message_ms is None:
            return False
        return self.clock_ms() - st.last_message_ms <= self.stale_after_s * 1000

    def state(self) -> str:
        if not self.symbols:
            return "inactive"
        if self.is_live():
            return "live"
        return "degraded"

    def status(self) -> dict[str, Any]:
        st = self.stats
        now = self.clock_ms()
        return {
            "state": self.state(),
            "connected": st.connected,
            "symbols": len(self.symbols),
            "connected_since_ms": st.connected_since_ms,
            "last_message_ms": st.last_message_ms,
            "last_message_age_s": None if st.last_message_ms is None else round((now - st.last_message_ms) / 1000, 3),
            "messages": st.messages,
            "reconnects": st.reconnects,
            "stale_events": st.stale_events,
            "rest_fallback": self.state() == "degraded",
            "rest_polls": st.rest_polls,
            "rest_errors": st.rest_errors,
            "last_rest_age_s": None if st.last_rest_ms is None else round((now - st.last_rest_ms) / 1000, 3),
            "stale_after_s": self.stale_after_s,
            "last_error": st.last_error,
        }

    # --- messages -----------------------------------------------------------------------------------

    def handle_message(self, text: str) -> LiveQuote | None:
        now = self.clock_ms()
        self.stats.last_message_ms = now
        self.stats.messages += 1
        q = parse_book_ticker_message(text, now)
        if q is not None:
            self._publish(q)
        return q

    def _publish(self, q: LiveQuote) -> None:
        self.cache.put(q)
        if self.on_quote is not None:
            try:
                self.on_quote(q)
            except Exception:
                logger.warning("live feed: on_quote failed for %s", q.symbol, exc_info=True)

    # --- boucle WebSocket ---------------------------------------------------------------------------

    async def run(self, stop: asyncio.Event) -> None:
        """Connexion, lecture, détection de flux figé, reconnexion avec backoff, jusqu'à ``stop``."""
        if not self.symbols:
            return
        backoff = 1.0
        first = True
        while not stop.is_set():
            if not first:
                self.stats.reconnects += 1
            first = False
            reason = "planned_reconnect"
            try:
                async with self.connect(self.stream_url) as ws:
                    self.stats.connected = True
                    self.stats.connected_since_ms = self.clock_ms()
                    got_message = False
                    started = time.monotonic()
                    while not stop.is_set() and time.monotonic() - started < PLANNED_RECONNECT_S:
                        try:
                            text = await asyncio.wait_for(ws.recv(), timeout=min(1.0, self.stale_after_s))
                        except TimeoutError:
                            text = None
                        if text is not None:
                            self.handle_message(text if isinstance(text, str) else text.decode())
                            if not got_message:  # backoff remis à zéro seulement sur un flux qui parle
                                got_message = True
                                backoff = 1.0
                            continue
                        last = self.stats.last_message_ms or self.stats.connected_since_ms or self.clock_ms()
                        if self.clock_ms() - last > self.stale_after_s * 1000:
                            self.stats.stale_events += 1
                            raise TimeoutError(f"flux figé : aucun message depuis {self.stale_after_s:g} s")
            except Exception as exc:  # noqa: BLE001 -- déconnexion, DNS, refus, flux figé…
                reason = f"{type(exc).__name__}: {exc}"
                self.stats.last_error = reason
                logger.warning("live feed: connexion perdue (%s)", reason)
            finally:
                self.stats.connected = False
            if stop.is_set():
                break
            if reason != "planned_reconnect":
                await self._wait(stop, backoff)
                backoff = min(backoff * 2, MAX_BACKOFF_S)

    async def _wait(self, stop: asyncio.Event, seconds: float) -> None:
        try:
            await asyncio.wait_for(stop.wait(), timeout=seconds)
        except TimeoutError:
            pass

    # --- retour au REST quand le flux est dégradé ---------------------------------------------------

    def poll_rest_once(self) -> int:
        """Un relevé REST bookTicker de tous les symboles (synchrone). Renvoie le nombre de prix publiés."""
        fetch = self.rest_fetch or self._rest_fetch_default
        now = self.clock_ms()
        try:
            rows = fetch(self.symbols)
        except Exception as exc:  # noqa: BLE001
            self.stats.rest_errors += 1
            self.stats.last_error = f"rest: {type(exc).__name__}: {exc}"
            return 0
        self.stats.rest_polls += 1
        self.stats.last_rest_ms = now
        quotes = parse_rest_book_tickers(rows, now)
        for q in quotes:
            self._publish(q)
        return len(quotes)

    def _rest_fetch_default(self, symbols: list[str]) -> Any:
        import httpx

        r = httpx.get(
            f"{self.rest_base}/api/v3/ticker/bookTicker",
            params={"symbols": json.dumps(symbols, separators=(",", ":"))},
            timeout=10.0,
        )
        r.raise_for_status()
        return r.json()

    async def rest_fallback_loop(self, stop: asyncio.Event) -> None:
        """Tant que le flux n'est pas « en direct », relève les prix par REST toutes les ``rest_poll_s``."""
        if not self.symbols:
            return
        while not stop.is_set():
            if not self.is_live():
                await asyncio.to_thread(self.poll_rest_once)
            await self._wait(stop, self.rest_poll_s)
