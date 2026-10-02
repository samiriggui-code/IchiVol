"""OB-1 — collecteur de carnet + transactions (service séparé de l'engine).

Lancement : ``python -m app.microstructure.book.collector`` (service ``orderbook-collector`` du compose).
Un plantage du collecteur n'arrête pas l'engine, et inversement : seuls les fichiers de ``OB_DATA_DIR``
sont partagés (lecture seule côté engine).

Flux publics Binance spot, sans compte :
- ``<symbol>@depth@100ms`` (diff depth) + snapshot REST ``/api/v3/depth`` → carnet synchronisé (``sync.py``) ;
- ``<symbol>@aggTrade`` → transactions avec côté agresseur ; trous comblés par REST ``aggTrades?fromId=``.
``bookTicker`` n'est pas abonné : le meilleur bid / ask se lit dans le carnet synchronisé, et ce flux
(plusieurs centaines de messages / s sur BTC) doublerait le volume brut sans information nouvelle.

Variables : ``OB_SYMBOLS`` (défaut ``BTCUSDT``), ``OB_DATA_DIR`` (``/data/orderbook``), ``OB_WS_BASE``,
``OB_REST_BASE``, ``OB_RAW`` (``1``), ``OB_RAW_RETENTION_DAYS`` (7), ``OB_AGG_RETENTION_DAYS`` (365),
``OB_SNAPSHOT_LIMIT`` (1000).
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import signal
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from app.microstructure.book.aggregate import AGG_VERSION, DEFAULT_BUCKET_WIDTH, MinuteAggregator
from app.microstructure.book.storage import DailyWriter, purge_older_than, write_status
from app.microstructure.book.sync import BookState, DepthEvent, LocalBook
from app.microstructure.book.trades import AggTrade, TradeTracker

logger = logging.getLogger("orderbook-collector")

COLLECTOR_VERSION = "ob-collector-v1"
VENUE = "binance-spot"
PLANNED_RECONNECT_S = 23 * 3600  # Binance ferme les WS au bout de 24 h
STATUS_EVERY_MS = 5000
MAX_BACKFILL = 1000


def _now_ms() -> int:
    return int(time.time() * 1000)


@dataclass
class CollectorConfig:
    symbol: str
    data_dir: Path
    ws_base: str = "wss://data-stream.binance.vision"
    rest_base: str = "https://data-api.binance.vision"
    snapshot_limit: int = 1000
    bucket_width: float = 10.0
    raw: bool = True
    raw_retention_days: int = 7
    agg_retention_days: int = 365

    @property
    def stream_url(self) -> str:
        s = self.symbol.lower()
        return f"{self.ws_base}/stream?streams={s}@depth@100ms/{s}@aggTrade"


@dataclass
class SymbolSession:
    """Traitement d'un symbole, sans réseau : messages entrants → carnet, trades, agrégats, fichiers.

    ``fetch_snapshot()`` et ``fetch_agg_trades(from_id)`` sont injectés (tests : faux flux)."""

    cfg: CollectorConfig
    fetch_snapshot: Callable[[], dict[str, Any]]
    fetch_agg_trades: Callable[[int], list[dict[str, Any]]]
    clock_ms: Callable[[], int] = _now_ms
    book: LocalBook = field(init=False)
    tracker: TradeTracker = field(init=False)
    agg: MinuteAggregator = field(init=False)
    connected_since_ms: int | None = None
    disconnects: int = 0
    snapshot_errors: int = 0
    last_error: str | None = None
    _next_sample_ms: int = 0
    _next_status_ms: int = 0
    _purged_day: str | None = None
    _next_snapshot_ms: int = 0
    _snapshot_backoff_ms: int = 2000

    def __post_init__(self) -> None:
        sym = self.cfg.symbol.upper()
        self.book = LocalBook(symbol=sym, venue=VENUE)
        self.tracker = TradeTracker()
        self.agg = MinuteAggregator(symbol=sym, venue=VENUE, bucket_width=self.cfg.bucket_width)
        self.raw = DailyWriter(self.cfg.data_dir, sym, "raw", compress=True) if self.cfg.raw else None
        self.agg_out = DailyWriter(self.cfg.data_dir, sym, "agg", compress=False)

    # --- connexion ---------------------------------------------------------------------------------

    def on_connect(self) -> None:
        now = self.clock_ms()
        self.connected_since_ms = now
        self.book.reset()
        self._raw({"k": "conn", "event": "open", "url": self.cfg.stream_url}, now)
        self.write_status(force=True)

    def on_disconnect(self, reason: str) -> None:
        now = self.clock_ms()
        self.disconnects += 1
        self.last_error = reason
        self.connected_since_ms = None
        self.book.reset()  # rien n'est interpolé pendant la coupure
        self.agg.note_gap("book", now)
        self._raw({"k": "conn", "event": "close", "reason": reason}, now)
        self.write_status(force=True)

    # --- messages ----------------------------------------------------------------------------------

    def needs_snapshot(self) -> bool:
        """Snapshot à demander : carnet inconnu, au moins un événement déjà bufferisé (procédure §1-2), et
        délai entre deux tentatives respecté (2 s, doublé à chaque échec jusqu'à 60 s)."""
        return (
            self.book.last_update_id is None
            and bool(self.book._buffer)
            and self.clock_ms() >= self._next_snapshot_ms
        )

    def on_message(self, text: str) -> None:
        now = self.clock_ms()
        msg = json.loads(text)
        data = msg.get("data", msg)
        stream = str(msg.get("stream", ""))
        etype = data.get("e")
        self.book.on_alive(now)
        if etype == "depthUpdate" or stream.endswith("@depth@100ms"):
            ev = DepthEvent.from_binance(data, received_ms=now)
            self._raw({"k": "d", "E": ev.event_ms, "U": ev.first_id, "u": ev.final_id,
                       "b": data.get("b", []), "a": data.get("a", [])}, now)
            r = self.book.on_event(ev)
            if r.gap:
                self.agg.note_gap("book", now)
                self._raw({"k": "gap", "kind": "book", "at_U": ev.first_id, "at_u": ev.final_id}, now)
        elif etype == "aggTrade" or stream.endswith("@aggTrade"):
            self._on_trade(AggTrade.from_binance(data, received_ms=now), now)

    def _on_trade(self, t: AggTrade, now: int) -> None:
        keep, gap = self.tracker.accept(t)
        if gap is not None:
            self._backfill(gap.from_id, gap.to_id, now)
        if not keep:
            return
        self._raw({"k": "t", "a": t.agg_id, "p": t.price, "q": t.qty, "T": t.trade_ms,
                   "m": not t.buyer_is_aggressor}, now)
        self.agg.add_trade(t)

    def _backfill(self, from_id: int, to_id: int, now: int) -> None:
        """Comble un trou d'aggTrades par REST (au plus MAX_BACKFILL) ; le reste est enregistré comme trou."""
        filled = 0
        try:
            rows = self.fetch_agg_trades(from_id)
        except Exception as exc:  # réseau : le trou reste un trou
            rows = []
            self.last_error = f"backfill: {exc}"
        for row in rows:
            t = AggTrade.from_binance(row, received_ms=now)
            if from_id <= t.agg_id <= to_id:
                self._raw({"k": "t", "a": t.agg_id, "p": t.price, "q": t.qty, "T": t.trade_ms,
                           "m": not t.buyer_is_aggressor, "backfill": True}, now)
                self.agg.add_trade(t)
                filled += 1
        missing = (to_id - from_id + 1) - filled
        self._raw({"k": "gap", "kind": "trades", "from": from_id, "to": to_id, "filled": filled,
                   "missing": missing}, now)
        if missing > 0:
            self.agg.note_gap("trades", now)

    def apply_snapshot(self) -> None:
        now = self.clock_ms()
        try:
            snap = self.fetch_snapshot()
        except Exception as exc:
            self.snapshot_errors += 1
            self.last_error = f"snapshot: {exc}"
            self._next_snapshot_ms = now + self._snapshot_backoff_ms
            self._snapshot_backoff_ms = min(self._snapshot_backoff_ms * 2, 60_000)
            return
        self._next_snapshot_ms = now + 2000
        self._snapshot_backoff_ms = 2000
        self._raw({"k": "s", "lastUpdateId": snap.get("lastUpdateId"), "bids": snap.get("bids", []),
                   "asks": snap.get("asks", [])}, now)
        r = self.book.apply_snapshot(snap)
        if r.gap:
            self.agg.note_gap("book", now)
            self._raw({"k": "resync", "reason": "snapshot_not_bridging_buffer"}, now)
        self.write_status(force=True)

    # --- horloge -----------------------------------------------------------------------------------

    def tick(self) -> None:
        """Échantillon 1 s du carnet, écriture des minutes terminées, statut, rétention (1 fois / jour)."""
        now = self.clock_ms()
        if now >= self._next_sample_ms:
            self.agg.sample(self.book, now)
            self._next_sample_ms = max(self._next_sample_ms + 1000, now - now % 1000 + 1000)
        for row in self.agg.finalize(now):
            self.agg_out.write(row, row["t"] * 1000)
        self.write_status()
        day = time.strftime("%Y-%m-%d", time.gmtime(now / 1000))
        if day != self._purged_day:
            self._purged_day = day
            purge_older_than(self.cfg.data_dir, "raw", self.cfg.raw_retention_days, now)
            purge_older_than(self.cfg.data_dir, "agg", self.cfg.agg_retention_days, now)

    def status(self) -> dict[str, Any]:
        now = self.clock_ms()
        b = self.book
        bb, ba, mid = b.best_bid(), b.best_ask(), b.mid()
        return {
            "collector_version": COLLECTOR_VERSION,
            "agg_version": AGG_VERSION,
            "venue": VENUE,
            "symbol": b.symbol,
            "state": b.refresh_state(now).value,
            "written_at_ms": now,
            "connected_since_ms": self.connected_since_ms,
            "last_update_id": b.last_update_id,
            "last_event_ms": b.last_event_ms,
            "last_received_ms": b.last_received_ms,
            "best_bid": bb[0] if bb else None,
            "best_ask": ba[0] if ba else None,
            "mid": mid,
            "spread_bps": ((ba[0] - bb[0]) / mid * 1e4) if (bb and ba and mid) else None,
            "levels": {"bids": len(b.bids), "asks": len(b.asks)},
            "coverage": {"bid_min": b.coverage_bid_min, "ask_max": b.coverage_ask_max},
            "resyncs": b.resyncs,
            "book_gaps": b.gaps,
            "trade_gaps": len(self.tracker.gaps),
            "trade_duplicates": self.tracker.duplicates,
            "late_trades": self.agg.late_trades,
            "disconnects": self.disconnects,
            "snapshot_errors": self.snapshot_errors,
            "last_error": self.last_error,
            "raw_enabled": self.raw is not None,
            "bucket_width": self.cfg.bucket_width,
            "snapshot_limit": self.cfg.snapshot_limit,
        }

    def write_status(self, force: bool = False) -> None:
        now = self.clock_ms()
        if force or now >= self._next_status_ms:
            write_status(self.cfg.data_dir, self.cfg.symbol, self.status())
            self._next_status_ms = now + STATUS_EVERY_MS

    def close(self) -> None:
        if self.raw is not None:
            self.raw.close()
        self.agg_out.close()

    def _raw(self, obj: dict[str, Any], now: int) -> None:
        if self.raw is not None:
            obj["rx"] = now
            self.raw.write(obj, now)


# --- réseau ----------------------------------------------------------------------------------------


def _rest_fetchers(cfg: CollectorConfig) -> tuple[Callable[[], dict[str, Any]], Callable[[int], list[dict[str, Any]]]]:
    import httpx

    def snapshot() -> dict[str, Any]:
        r = httpx.get(f"{cfg.rest_base}/api/v3/depth",
                      params={"symbol": cfg.symbol.upper(), "limit": cfg.snapshot_limit}, timeout=10.0)
        r.raise_for_status()
        return r.json()

    def agg_trades(from_id: int) -> list[dict[str, Any]]:
        r = httpx.get(f"{cfg.rest_base}/api/v3/aggTrades",
                      params={"symbol": cfg.symbol.upper(), "fromId": from_id, "limit": MAX_BACKFILL}, timeout=10.0)
        r.raise_for_status()
        return r.json()

    return snapshot, agg_trades


async def run_symbol(cfg: CollectorConfig, stop: asyncio.Event) -> None:
    from websockets.asyncio.client import connect

    fetch_snapshot, fetch_trades = _rest_fetchers(cfg)
    session = SymbolSession(cfg, fetch_snapshot=fetch_snapshot, fetch_agg_trades=fetch_trades)
    backoff = 1.0
    try:
        while not stop.is_set():
            reason = "planned_reconnect"
            try:
                async with connect(cfg.stream_url, open_timeout=15, ping_interval=20, max_size=2**23) as ws:
                    session.on_connect()
                    backoff = 1.0
                    started = time.monotonic()
                    while not stop.is_set() and time.monotonic() - started < PLANNED_RECONNECT_S:
                        try:
                            text = await asyncio.wait_for(ws.recv(), timeout=0.25)
                        except TimeoutError:
                            text = None
                        if text is not None:
                            session.on_message(text if isinstance(text, str) else text.decode())
                            if session.needs_snapshot():
                                # Les événements arrivés pendant l'appel restent dans la file du WS et sont
                                # appliqués ensuite, dans l'ordre (ceux couverts par le snapshot sont ignorés).
                                await asyncio.to_thread(session.apply_snapshot)
                        session.tick()
            except Exception as exc:  # déconnexion, DNS, refus, timeout…
                reason = f"{type(exc).__name__}: {exc}"
                logger.warning("orderbook %s: connection lost (%s)", cfg.symbol, reason)
            if stop.is_set():
                session.on_disconnect("stopped")
                break
            session.on_disconnect(reason)
            if reason != "planned_reconnect":
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 30.0)
    finally:
        session.close()


def configs_from_env() -> list[CollectorConfig]:
    data_dir = Path(os.environ.get("OB_DATA_DIR", "/data/orderbook"))
    out = []
    for sym in [s.strip().upper() for s in os.environ.get("OB_SYMBOLS", "BTCUSDT").split(",") if s.strip()]:
        out.append(
            CollectorConfig(
                symbol=sym,
                data_dir=data_dir,
                ws_base=os.environ.get("OB_WS_BASE", "wss://data-stream.binance.vision"),
                rest_base=os.environ.get("OB_REST_BASE", "https://data-api.binance.vision"),
                snapshot_limit=int(os.environ.get("OB_SNAPSHOT_LIMIT", "1000")),
                bucket_width=float(os.environ.get(f"OB_BUCKET_{sym}", DEFAULT_BUCKET_WIDTH.get(sym, 1.0))),
                raw=os.environ.get("OB_RAW", "1") not in ("0", "false", "False"),
                raw_retention_days=int(os.environ.get("OB_RAW_RETENTION_DAYS", "7")),
                agg_retention_days=int(os.environ.get("OB_AGG_RETENTION_DAYS", "365")),
            )
        )
    return out


async def main() -> None:
    logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO").upper(),
                        format="%(asctime)s %(levelname)s %(name)s %(message)s")
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop.set)
        except NotImplementedError:  # Windows
            pass
    cfgs = configs_from_env()
    logger.info("orderbook collector %s: %s", COLLECTOR_VERSION, ", ".join(c.symbol for c in cfgs))
    await asyncio.gather(*(run_symbol(c, stop) for c in cfgs))


if __name__ == "__main__":
    asyncio.run(main())
