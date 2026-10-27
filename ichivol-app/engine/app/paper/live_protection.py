"""Stops et objectifs en temps réel des lots crypto ouverts du compte unique (flux direct Binance).

Complète, sans les remplacer, les deux contrôles existants :
- ``app/paper/engine.py::sync_position`` (scan toutes les 300 s, ``broker.check_stop_or_tp`` sur le dernier prix) ;
- ``app/paper/protection.py`` (toutes les 60 s, minutes 1m clôturées via REST).
Ces deux chemins restent actifs : si le flux direct est coupé ou dégradé, ils continuent de protéger les lots.

Déclenchement comme chez un courtier (règle unique : ``evaluate_live_trigger``) :
- LONG : stop si bid <= stop, objectif si bid >= objectif ; exécution au bid ;
- SHORT : stop si ask >= stop, objectif si ask <= objectif ; exécution à l'ask.
Le stop déclenché devient un ordre au marché : il s'exécute au dernier bid (LONG) / ask (SHORT) connu au moment
de la clôture, donc au stop ou PIRE en cas de saut de prix, jamais au stop idéal. L'objectif s'exécute au prix
qui l'a déclenché (au moins l'objectif).

Clôture : uniquement ``broker.close_capital_position`` (verrou de ligne du compte, grand livre, ordre, journal,
mêmes frais et même friction de profil que le scan). Le lot est relu SOUS le verrou : s'il a été fermé entre-
temps (scan, moniteur 1m, ordre manuel, second message), rien n'est écrit. Motif ``stop_hit`` /
``take_profit_hit`` (libellés existants du front) ; l'événement CLOSED porte ``trigger="live"`` et le détail du
prix (bid / ask, âge, saut), ce qui distingue ces sorties dans le journal.

Ne touche à aucune règle d'entrée : les décisions restent prises sur bougies 1h clôturées.
"""

from __future__ import annotations

import logging
import queue
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import PaperPortfolio, PaperPosition
from app.market_data.binance_live import LivePriceCache, LiveQuote, now_ms
from app.paper import broker as paper_broker

logger = logging.getLogger(__name__)

TRIGGER_TAG = "live"


@dataclass(frozen=True)
class LiveTrigger:
    reason: str  # stop_hit | take_profit_hit
    level: float  # stop ou objectif franchi
    side: str  # bid | ask
    price: float  # bid (LONG) / ask (SHORT) qui a déclenché


def evaluate_live_trigger(
    direction: str, stop: float | None, target: float | None, bid: float, ask: float
) -> LiveTrigger | None:
    """Règle de déclenchement unique (stop prioritaire). Aucun niveau manquant n'est deviné."""
    if stop is None or target is None:
        return None
    if direction.upper() == "LONG":
        if bid <= stop:
            return LiveTrigger("stop_hit", float(stop), "bid", bid)
        if bid >= target:
            return LiveTrigger("take_profit_hit", float(target), "bid", bid)
        return None
    if ask >= stop:
        return LiveTrigger("stop_hit", float(stop), "ask", ask)
    if ask <= target:
        return LiveTrigger("take_profit_hit", float(target), "ask", ask)
    return None


def execution_price(direction: str, trigger: LiveTrigger, trigger_quote: LiveQuote, latest: LiveQuote | None) -> tuple[float, LiveQuote]:
    """Prix d'exécution et quote utilisée.

    Stop = ordre au marché : dernier côté connu (plus récent que le déclenchement s'il existe), et jamais
    meilleur que le côté qui a déclenché (un rebond entre le déclenchement et la clôture ne sauve pas le lot :
    LONG → min des deux bids, SHORT → max des deux asks). Objectif : prix du déclenchement (>= objectif LONG,
    <= objectif SHORT)."""
    long = direction.upper() == "LONG"
    if trigger.reason != "stop_hit" or latest is None or latest.received_ms < trigger_quote.received_ms:
        return trigger.price, trigger_quote
    side_latest = latest.bid if long else latest.ask
    if long:
        return (side_latest, latest) if side_latest < trigger.price else (trigger.price, trigger_quote)
    return (side_latest, latest) if side_latest > trigger.price else (trigger.price, trigger_quote)


def _managed_by_minute_monitor(pos: PaperPosition, portfolio: PaperPortfolio | None) -> bool:
    """Lots à stop suiveur / prises partielles / renforts : leur gestion (ordre stop > partielles > objectif,
    garde « net de frais » du stop suiveur) vit dans ``protection.py`` ; le flux direct ne les ferme pas."""
    from app.paper.protection_partial_tp import resolve_paper_partial_tp
    from app.paper.protection_reinforce import resolve_paper_reinforce
    from app.paper.protection_trail import resolve_paper_trail

    try:
        return any(fn(pos, portfolio) is not None for fn in (resolve_paper_trail, resolve_paper_partial_tp, resolve_paper_reinforce))
    except Exception:  # noqa: BLE001 -- configuration illisible : on laisse le moniteur 1m décider
        return True


def close_lot_on_quote(
    session: Session,
    position_id: str,
    trigger_quote: LiveQuote,
    *,
    latest: LiveQuote | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Ferme un lot si, relu sous le verrou du compte, il est encore ouvert et que ses niveaux ACTUELS sont
    franchis par ``trigger_quote``. Valide la transaction. Idempotent : un lot ne se ferme qu'une fois."""
    pos = session.get(PaperPosition, position_id, populate_existing=True)
    if pos is None or pos.status != "OPEN" or not pos.qty:
        session.rollback()
        return {"id": position_id, "status": "already_closed"}
    portfolio = session.get(PaperPortfolio, pos.portfolio_id) if pos.portfolio_id else None
    paper_broker.lock_portfolio(session, portfolio)  # tout écrivain de caisse passe par ce verrou
    session.refresh(pos)
    if pos.status != "OPEN" or not pos.qty:
        session.rollback()
        return {"id": position_id, "status": "already_closed"}
    trig = evaluate_live_trigger(pos.direction, pos.stop_price, pos.take_profit_price, trigger_quote.bid, trigger_quote.ask)
    if trig is None:  # niveaux déplacés entre-temps (stop suiveur, modification)
        session.rollback()
        return {"id": position_id, "status": "levels_changed"}
    price, used = execution_price(pos.direction, trig, trigger_quote, latest)
    at = now or datetime.now(UTC)
    at_ms = int(at.timestamp() * 1000)
    long = pos.direction.upper() == "LONG"
    gapped = (price < trig.level if long else price > trig.level) if trig.reason == "stop_hit" else (
        price > trig.level if long else price < trig.level
    )
    live = {
        "source": f"binance_{used.source}",
        "bid": used.bid,
        "ask": used.ask,
        "side": trig.side,
        "level": trig.level,
        "trigger_price": trig.price,
        "execution_price_before_friction": price,
        "gap": gapped,
        "quote_received_at": datetime.fromtimestamp(used.received_ms / 1000, UTC).isoformat(),
        "quote_age_ms": max(0, at_ms - used.received_ms),
    }
    paper_broker.close_capital_position(
        session, pos, price=price, reason=trig.reason,
        signal={"protection": {"reason": trig.reason, "trigger": TRIGGER_TAG, **live}},
        at=at,
        journal_extra={"trigger": TRIGGER_TAG, "live": live},
    )
    closed = pos.status == "CLOSED"
    session.commit()
    return {
        "id": position_id, "status": "closed" if closed else "already_closed", "reason": trig.reason,
        "symbol": pos.symbol, "price": price, "exit_fill": pos.exit_price, "gap": gapped,
    }


@dataclass(frozen=True)
class WatchedLot:
    position_id: str
    symbol: str  # symbole du flux (provider)
    direction: str
    stop: float
    target: float


class LiveProtector:
    """Surveille en mémoire les lots crypto ouverts ; délègue chaque clôture à un thread unique.

    ``on_quote`` (boucle du flux) ne fait qu'une comparaison ; la clôture (base de données) se fait dans
    ``worker``. Un lot déjà en file n'y est remis qu'après traitement (pas de rafale de clôtures)."""

    def __init__(
        self,
        cache: LivePriceCache,
        *,
        symbol_map: dict[str, str],
        portfolio_code: str,
        session_factory: Callable[[], Session] | None = None,
        refresh_s: float = 5.0,
    ) -> None:
        self.cache = cache
        self.symbol_map = dict(symbol_map)  # symbole du compte -> symbole du flux
        self.portfolio_code = portfolio_code
        self._session_factory = session_factory
        self.refresh_s = refresh_s
        self._lock = threading.Lock()
        self._lots: dict[str, list[WatchedLot]] = {}
        self._pending: set[str] = set()
        self._queue: queue.Queue[tuple[WatchedLot, LiveQuote]] = queue.Queue()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.closes = 0
        self.skipped_managed = 0
        self.errors = 0
        self.last_refresh_ms: int | None = None
        self.last_close: dict[str, Any] | None = None
        self.last_error: str | None = None

    def _session(self) -> Session:
        if self._session_factory is not None:
            return self._session_factory()
        from app.db.session import SessionLocal

        return SessionLocal()

    # --- lots surveillés ----------------------------------------------------------------------------

    def refresh_lots(self, session: Session) -> int:
        pf = session.execute(select(PaperPortfolio).where(PaperPortfolio.code == self.portfolio_code)).scalar_one_or_none()
        lots: dict[str, list[WatchedLot]] = {}
        skipped = 0
        if pf is not None:
            rows = session.execute(
                select(PaperPosition).where(
                    PaperPosition.portfolio_id == pf.id,
                    PaperPosition.status == "OPEN",
                    PaperPosition.symbol.in_(list(self.symbol_map)),
                )
            ).scalars().all()
            for pos in rows:
                if not pos.qty or pos.stop_price is None or pos.take_profit_price is None:
                    continue
                if _managed_by_minute_monitor(pos, pf):
                    skipped += 1
                    continue
                feed_sym = self.symbol_map[pos.symbol]
                lots.setdefault(feed_sym, []).append(
                    WatchedLot(pos.id, feed_sym, pos.direction, float(pos.stop_price), float(pos.take_profit_price))
                )
        session.rollback()  # lecture seule
        with self._lock:
            self._lots = lots
            self.skipped_managed = skipped
        self.last_refresh_ms = now_ms()
        return sum(len(v) for v in lots.values())

    def watched(self) -> list[WatchedLot]:
        with self._lock:
            return [lot for lots in self._lots.values() for lot in lots]

    # --- prix entrants (boucle du flux) -------------------------------------------------------------

    def on_quote(self, q: LiveQuote) -> None:
        with self._lock:
            lots = self._lots.get(q.symbol)
            if not lots:
                return
            for lot in lots:
                if lot.position_id in self._pending:
                    continue
                if evaluate_live_trigger(lot.direction, lot.stop, lot.target, q.bid, q.ask) is None:
                    continue
                self._pending.add(lot.position_id)
                self._queue.put((lot, q))

    # --- clôtures (thread unique) -------------------------------------------------------------------

    def process_next(self, timeout: float = 0.5) -> dict[str, Any] | None:
        try:
            lot, q = self._queue.get(timeout=timeout)
        except queue.Empty:
            return None
        session = self._session()
        try:
            res = close_lot_on_quote(session, lot.position_id, q, latest=self.cache.get(lot.symbol))
            if res["status"] == "closed":
                self.closes += 1
                self.last_close = {**res, "at_ms": now_ms()}
                logger.info("live protection: %s", res)
            if res["status"] in ("closed", "already_closed"):
                with self._lock:  # plus jamais surveillé, même avant le prochain rafraîchissement
                    self._lots[lot.symbol] = [x for x in self._lots.get(lot.symbol, []) if x.position_id != lot.position_id]
            return res
        except Exception as exc:
            session.rollback()
            self.errors += 1
            self.last_error = f"{type(exc).__name__}: {exc}"[:200]
            logger.warning("live protection: %s failed", lot.position_id, exc_info=True)
            return {"id": lot.position_id, "status": "error", "error": self.last_error}
        finally:
            session.close()
            with self._lock:
                self._pending.discard(lot.position_id)

    def _loop(self) -> None:
        next_refresh = 0.0
        while not self._stop.is_set():
            if time.monotonic() >= next_refresh:
                session = self._session()
                try:
                    self.refresh_lots(session)
                except Exception as exc:
                    session.rollback()
                    self.errors += 1
                    self.last_error = f"refresh: {type(exc).__name__}: {exc}"[:200]
                    logger.warning("live protection: refresh failed", exc_info=True)
                finally:
                    session.close()
                next_refresh = time.monotonic() + self.refresh_s
            self.process_next(timeout=0.5)

    def start(self) -> None:
        if self._thread is not None:
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._loop, daemon=True, name="live-protection")
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def status(self) -> dict[str, Any]:
        with self._lock:
            n = sum(len(v) for v in self._lots.values())
            pending = len(self._pending)
        return {
            "watched_lots": n,
            "skipped_managed_lots": self.skipped_managed,
            "pending_closes": pending,
            "closes": self.closes,
            "errors": self.errors,
            "last_refresh_ms": self.last_refresh_ms,
            "last_close": self.last_close,
            "last_error": self.last_error,
        }
