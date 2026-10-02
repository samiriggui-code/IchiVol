"""OB-1 — flux aggTrades : contrôle de continuité (ids consécutifs), doublons, trous.

``a`` (aggTrade id) est consécutif chez Binance : un saut = des transactions manquantes, comblées par REST
``/api/v3/aggTrades?fromId=`` quand c'est possible, sinon enregistrées comme trou (jamais inventées).
``m`` = l'acheteur est maker → l'agresseur est **vendeur**. Un aggTrade agrège les fills d'un même ordre taker
au même prix : ce n'est pas « un ordre » au sens strict.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class AggTrade:
    agg_id: int
    price: float
    qty: float
    trade_ms: int
    buyer_is_aggressor: bool
    received_ms: int | None = None

    @classmethod
    def from_binance(cls, msg: dict[str, Any], received_ms: int | None = None) -> "AggTrade":
        return cls(
            agg_id=int(msg["a"]),
            price=float(msg["p"]),
            qty=float(msg["q"]),
            trade_ms=int(msg["T"]),
            buyer_is_aggressor=not bool(msg["m"]),
            received_ms=received_ms,
        )


@dataclass(frozen=True)
class TradeGap:
    from_id: int  # premier id manquant
    to_id: int  # dernier id manquant (inclus)


@dataclass
class TradeTracker:
    last_id: int | None = None
    duplicates: int = 0
    gaps: list[TradeGap] = field(default_factory=list)

    def accept(self, t: AggTrade) -> tuple[bool, TradeGap | None]:
        """(à garder ?, trou détecté avant ce trade). Un doublon (id déjà vu) est ignoré."""
        if self.last_id is not None and t.agg_id <= self.last_id:
            self.duplicates += 1
            return False, None
        gap = None
        if self.last_id is not None and t.agg_id > self.last_id + 1:
            gap = TradeGap(self.last_id + 1, t.agg_id - 1)
            self.gaps.append(gap)
        self.last_id = t.agg_id
        return True, gap
