"""OB-1 — carnet local synchronisé snapshot + deltas (Binance spot), logique pure sans I/O.

Étude : docs/ETUDE-ORDERFLOW-MTF-2026-10-02.md §3.3. Procédure Binance spot (diff depth stream) :
1. ouvrir le flux diff et **bufferiser** ;
2. snapshot REST ``/api/v3/depth`` → ``lastUpdateId`` ;
3. jeter les événements ``u <= lastUpdateId`` ;
4. le premier événement appliqué doit vérifier ``U <= lastUpdateId + 1 <= u`` (sinon : nouveau snapshot) ;
5. chaque événement suivant : ``U == u_précédent + 1``, sinon trou → ``PARTIAL`` + resynchronisation ;
6. quantité 0 = niveau supprimé ; un niveau hors de la profondeur du snapshot reste **inconnu**, pas vide.

Le carnet est celui d'**une** plateforme et d'**un** instrument : il ne représente pas tout le marché.
Une disparition de niveau n'est pas une exécution (elle peut être une annulation).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Iterable, Sequence


class BookState(str, Enum):
    SYNCED = "SYNCED"  # snapshot appliqué, séquence continue, événement récent
    PARTIAL = "PARTIAL"  # trou de séquence / resynchronisation en cours
    STALE = "STALE"  # flux censé ouvert mais muet depuis plus que le seuil
    UNAVAILABLE = "UNAVAILABLE"  # pas (encore) de carnet


STALE_AFTER_MS = 2000


@dataclass(frozen=True)
class DepthEvent:
    first_id: int  # U
    final_id: int  # u
    bids: tuple[tuple[float, float], ...]
    asks: tuple[tuple[float, float], ...]
    event_ms: int | None = None  # E (heure plateforme)
    received_ms: int | None = None

    @classmethod
    def from_binance(cls, msg: dict[str, Any], received_ms: int | None = None) -> "DepthEvent":
        return cls(
            first_id=int(msg["U"]),
            final_id=int(msg["u"]),
            bids=tuple((float(p), float(q)) for p, q in msg.get("b", [])),
            asks=tuple((float(p), float(q)) for p, q in msg.get("a", [])),
            event_ms=int(msg["E"]) if "E" in msg else None,
            received_ms=received_ms,
        )


@dataclass
class ApplyResult:
    applied: int = 0
    ignored_old: int = 0
    gap: bool = False
    need_snapshot: bool = False


@dataclass
class LocalBook:
    symbol: str
    venue: str = "binance-spot"
    bids: dict[float, float] = field(default_factory=dict)
    asks: dict[float, float] = field(default_factory=dict)
    last_update_id: int | None = None
    state: BookState = BookState.UNAVAILABLE
    # Profondeur couverte par le dernier snapshot : au-delà, un niveau absent est inconnu.
    coverage_bid_min: float | None = None
    coverage_ask_max: float | None = None
    last_event_ms: int | None = None
    last_received_ms: int | None = None
    resyncs: int = 0
    gaps: int = 0
    _buffer: list[DepthEvent] = field(default_factory=list)
    _awaiting_first: bool = True

    # --- cycle de synchronisation ------------------------------------------------------------------

    def reset(self) -> None:
        """Déconnexion / resynchronisation : on repart d'un carnet inconnu (rien d'interpolé)."""
        self.bids.clear()
        self.asks.clear()
        self.last_update_id = None
        self.coverage_bid_min = self.coverage_ask_max = None
        self._buffer.clear()
        self._awaiting_first = True
        self.state = BookState.UNAVAILABLE

    def on_event(self, ev: DepthEvent) -> ApplyResult:
        """Événement diff. Avant le snapshot : bufferisé. Après : appliqué avec contrôle de séquence."""
        if ev.received_ms is not None:
            self.last_received_ms = ev.received_ms
        if self.last_update_id is None:
            self._buffer.append(ev)
            return ApplyResult()
        return self._apply(ev)

    def apply_snapshot(self, snapshot: dict[str, Any]) -> ApplyResult:
        """Snapshot REST ``{"lastUpdateId", "bids", "asks"}`` puis rejoue le buffer selon la procédure."""
        self.bids = {float(p): float(q) for p, q in snapshot.get("bids", []) if float(q) > 0}
        self.asks = {float(p): float(q) for p, q in snapshot.get("asks", []) if float(q) > 0}
        self.last_update_id = int(snapshot["lastUpdateId"])
        self.coverage_bid_min = min(self.bids) if self.bids else None
        self.coverage_ask_max = max(self.asks) if self.asks else None
        self._awaiting_first = True
        self.state = BookState.PARTIAL  # SYNCED seulement après le premier événement valide
        buffered, self._buffer = self._buffer, []
        total = ApplyResult()
        for i, ev in enumerate(buffered):
            r = self._apply(ev)
            total.applied += r.applied
            total.ignored_old += r.ignored_old
            if r.gap or r.need_snapshot:
                total.gap, total.need_snapshot = r.gap, r.need_snapshot
                # Keep the failing event and the ones after it: a newer snapshot will still need them.
                self._buffer = list(buffered[i:])
                break
        return total

    def _apply(self, ev: DepthEvent) -> ApplyResult:
        assert self.last_update_id is not None
        if ev.final_id <= self.last_update_id:
            return ApplyResult(ignored_old=1)
        if self._awaiting_first:
            if not (ev.first_id <= self.last_update_id + 1 <= ev.final_id):
                # Le snapshot est plus récent que le buffer, ou un événement manque : nouveau snapshot.
                self._mark_gap()
                return ApplyResult(gap=True, need_snapshot=True)
            self._awaiting_first = False
        elif ev.first_id != self.last_update_id + 1:
            self._mark_gap()
            return ApplyResult(gap=True, need_snapshot=True)
        _update_side(self.bids, ev.bids)
        _update_side(self.asks, ev.asks)
        self.last_update_id = ev.final_id
        if ev.event_ms is not None:
            self.last_event_ms = ev.event_ms
        self.state = BookState.SYNCED
        return ApplyResult(applied=1)

    def _mark_gap(self) -> None:
        self.gaps += 1
        self.resyncs += 1
        self.reset()
        self.state = BookState.PARTIAL

    def refresh_state(self, now_ms: int) -> BookState:
        """SYNCED devient STALE si plus rien n'arrive depuis ``STALE_AFTER_MS`` (horloge de réception)."""
        if self.state == BookState.SYNCED and self.last_received_ms is not None:
            if now_ms - self.last_received_ms > STALE_AFTER_MS:
                self.state = BookState.STALE
        return self.state

    def on_alive(self, received_ms: int) -> None:
        """Un message arrive après un silence : STALE redevient SYNCED (la séquence, elle, est vérifiée)."""
        self.last_received_ms = received_ms
        if self.state == BookState.STALE and self.last_update_id is not None and not self._awaiting_first:
            self.state = BookState.SYNCED

    # --- lectures ----------------------------------------------------------------------------------

    def best_bid(self) -> tuple[float, float] | None:
        if not self.bids:
            return None
        p = max(self.bids)
        return p, self.bids[p]

    def best_ask(self) -> tuple[float, float] | None:
        if not self.asks:
            return None
        p = min(self.asks)
        return p, self.asks[p]

    def mid(self) -> float | None:
        b, a = self.best_bid(), self.best_ask()
        if b is None or a is None or b[0] >= a[0]:
            return None
        return (b[0] + a[0]) / 2

    def covers(self, low: float, high: float) -> bool:
        """La plage [low, high] est-elle dans la profondeur connue (sinon : mesure partielle) ?"""
        if self.coverage_bid_min is None or self.coverage_ask_max is None:
            return False
        return low >= self.coverage_bid_min and high <= self.coverage_ask_max

    def depth_within(self, pct: float) -> tuple[float, float, bool] | None:
        """(Σ qté bid, Σ qté ask) dans ±pct du mid, et ``covered`` (plage dans la profondeur du snapshot)."""
        mid = self.mid()
        if mid is None:
            return None
        lo, hi = mid * (1 - pct), mid * (1 + pct)
        bid = sum(q for p, q in self.bids.items() if p >= lo)
        ask = sum(q for p, q in self.asks.items() if p <= hi)
        return bid, ask, self.covers(lo, hi)

    def bucketed(self, width: float, pct: float) -> dict[float, tuple[float, float]]:
        """Quantités agrégées par bucket de prix (borne basse multiple de ``width``) dans ±pct du mid."""
        mid = self.mid()
        out: dict[float, list[float]] = {}
        if mid is None or width <= 0:
            return {}
        lo, hi = mid * (1 - pct), mid * (1 + pct)
        for side, levels in ((0, self.bids), (1, self.asks)):
            for p, q in levels.items():
                if lo <= p <= hi:
                    b = round((p // width) * width, 8)
                    out.setdefault(b, [0.0, 0.0])[side] += q
        return {b: (v[0], v[1]) for b, v in out.items()}


def _update_side(side: dict[float, float], levels: Iterable[Sequence[float]]) -> None:
    for p, q in levels:
        if q == 0:
            side.pop(p, None)
        else:
            side[p] = q
