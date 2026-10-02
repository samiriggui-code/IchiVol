"""OB-1 — agrégat 1 minute : grille (bucket de prix × minute) du carnet et des transactions.

Calculé **depuis les données reçues**, jamais extrapolé :
- carnet : échantillonné chaque seconde, **seulement quand il est SYNCED** ; moyenne par bucket sur les
  secondes synchronisées ; l'état de la minute dit combien de secondes l'étaient ;
- transactions : sommes par côté agresseur et par bucket (``X_buy`` / ``X_sell``).

Une minute sans carnet synchronisé a ``book_state != SYNCED`` et des niveaux vides : c'est « non mesuré »,
pas « carnet vide ». Paramètres figés a priori (largeur de bucket, plage ±1 %, seuils d'état), versionnés.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from app.microstructure.book.sync import BookState, LocalBook
from app.microstructure.book.trades import AggTrade

AGG_VERSION = "ob-agg-v1"
RANGE_PCT = 0.01  # niveaux retenus : ±1 % autour du mid
NEAR_PCT = 0.001  # profondeur « proche » : ±0,1 % (10 pb)
SYNCED_MIN_SAMPLES = 55  # ≥ 55 s synchronisées sur 60 → minute SYNCED
FINALIZE_GRACE_MS = 2000  # trades d'une minute encore acceptés 2 s après sa fin
# Largeur de bucket par instrument, figée avant collecte (≈ 1 pb du prix BTC fin 2026).
DEFAULT_BUCKET_WIDTH: dict[str, float] = {"BTCUSDT": 10.0, "ETHUSDT": 0.5, "SOLUSDT": 0.02}


def bucket_of(price: float, width: float) -> float:
    return round((price // width) * width, 8)


@dataclass
class _Minute:
    start_ms: int
    samples: dict[str, int] = field(default_factory=lambda: {s.value: 0 for s in BookState})
    level_sums: dict[float, list[float]] = field(default_factory=dict)  # bucket -> [Σq_bid, Σq_ask]
    spread_bps: list[float] = field(default_factory=list)
    mids: list[float] = field(default_factory=list)
    near_bid: list[float] = field(default_factory=list)
    near_ask: list[float] = field(default_factory=list)
    near_covered: bool = True
    range_covered: bool = True
    trade_n: int = 0
    buy_qty: float = 0.0
    sell_qty: float = 0.0
    notional: float = 0.0
    max_qty: float = 0.0
    trade_buckets: dict[float, list[float]] = field(default_factory=dict)  # bucket -> [buy, sell]
    trade_gaps: int = 0
    book_gaps: int = 0


@dataclass
class MinuteAggregator:
    symbol: str
    venue: str = "binance-spot"
    bucket_width: float = 10.0
    range_pct: float = RANGE_PCT
    _open: dict[int, _Minute] = field(default_factory=dict)
    late_trades: int = 0
    _finalized_until_ms: int = 0

    def _minute(self, t_ms: int) -> _Minute | None:
        start = t_ms - t_ms % 60_000
        if start < self._finalized_until_ms:
            return None  # minute déjà écrite
        if start not in self._open:
            self._open[start] = _Minute(start_ms=start)
        return self._open[start]

    def sample(self, book: LocalBook, now_ms: int) -> None:
        """Échantillon 1 s. Le carnet n'est lu que s'il est SYNCED (sinon seul l'état est compté)."""
        m = self._minute(now_ms)
        if m is None:
            return
        state = book.refresh_state(now_ms)
        m.samples[state.value] += 1
        if state != BookState.SYNCED:
            return
        mid = book.mid()
        bb, ba = book.best_bid(), book.best_ask()
        if mid is None or bb is None or ba is None:
            return
        m.mids.append(mid)
        m.spread_bps.append((ba[0] - bb[0]) / mid * 1e4)
        near = book.depth_within(NEAR_PCT)
        if near is not None:
            m.near_bid.append(near[0])
            m.near_ask.append(near[1])
            m.near_covered = m.near_covered and near[2]
        m.range_covered = m.range_covered and book.covers(mid * (1 - self.range_pct), mid * (1 + self.range_pct))
        for b, (qb, qa) in book.bucketed(self.bucket_width, self.range_pct).items():
            acc = m.level_sums.setdefault(b, [0.0, 0.0])
            acc[0] += qb
            acc[1] += qa

    def add_trade(self, t: AggTrade) -> bool:
        m = self._minute(t.trade_ms)
        if m is None:
            self.late_trades += 1
            return False
        m.trade_n += 1
        if t.buyer_is_aggressor:
            m.buy_qty += t.qty
        else:
            m.sell_qty += t.qty
        m.notional += t.qty * t.price
        m.max_qty = max(m.max_qty, t.qty)
        acc = m.trade_buckets.setdefault(bucket_of(t.price, self.bucket_width), [0.0, 0.0])
        acc[0 if t.buyer_is_aggressor else 1] += t.qty
        return True

    def note_gap(self, kind: str, at_ms: int) -> None:
        m = self._minute(at_ms)
        if m is None:
            return
        if kind == "trades":
            m.trade_gaps += 1
        else:
            m.book_gaps += 1

    def finalize(self, now_ms: int) -> list[dict[str, Any]]:
        """Minutes terminées (fin + délai de grâce ≤ now), dans l'ordre. Elles ne sont plus modifiables."""
        rows = []
        for start in sorted(self._open):
            if start + 60_000 + FINALIZE_GRACE_MS > now_ms:
                break
            rows.append(self._row(self._open.pop(start)))
            self._finalized_until_ms = start + 60_000
        return rows

    def _row(self, m: _Minute) -> dict[str, Any]:
        synced = m.samples[BookState.SYNCED.value]
        if synced >= SYNCED_MIN_SAMPLES:
            state = BookState.SYNCED.value
        elif synced > 0 or m.samples[BookState.PARTIAL.value] > 0:
            state = BookState.PARTIAL.value
        elif m.samples[BookState.STALE.value] > 0:
            state = BookState.STALE.value
        else:
            state = BookState.UNAVAILABLE.value
        n = len(m.mids)

        def mean(xs: list[float]) -> float | None:
            return sum(xs) / len(xs) if xs else None

        traded = m.buy_qty + m.sell_qty
        return {
            "v": AGG_VERSION,
            "t": m.start_ms // 1000,
            "venue": self.venue,
            "symbol": self.symbol,
            "book_state": state,
            "samples": dict(m.samples),
            "mid_last": m.mids[-1] if m.mids else None,
            "mid_mean": mean(m.mids),
            "spread_bps_mean": mean(m.spread_bps),
            "spread_bps_max": max(m.spread_bps) if m.spread_bps else None,
            "depth_10bp": {
                "bid": mean(m.near_bid),
                "ask": mean(m.near_ask),
                "covered": bool(m.near_bid) and m.near_covered,
            },
            "range_pct": self.range_pct,
            "range_covered": n > 0 and m.range_covered,
            "bucket_width": self.bucket_width,
            # [borne basse du bucket, qté bid moyenne, qté ask moyenne] sur les secondes SYNCED
            "levels": [
                [b, round(v[0] / n, 8), round(v[1] / n, 8)] for b, v in sorted(m.level_sums.items())
            ] if n else [],
            "trades": {
                "n": m.trade_n,
                "buy_qty": m.buy_qty,
                "sell_qty": m.sell_qty,
                "delta": m.buy_qty - m.sell_qty,
                "vwap": (m.notional / traded) if traded > 0 else None,
                "max_qty": m.max_qty,
                "by_bucket": [[b, v[0], v[1]] for b, v in sorted(m.trade_buckets.items())],
            },
            "trade_gaps": m.trade_gaps,
            "book_gaps": m.book_gaps,
        }
