"""Références passives RS-03 §7 : B0-F (détention pleinement investie) et B0-E (exposition réduite)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Sequence

from app.indicators.ichimoku import Candle

from rs import INITIAL_CAPITAL, SCORE_START
from rs.costs import SymbolCost


def _month(t: int) -> tuple[int, int]:
    d = datetime.fromtimestamp(t, tz=timezone.utc)
    return d.year, d.month


def passive(
    candles_by_sym: dict[str, Sequence[Candle]],
    costs: dict[str, SymbolCost],
    *,
    weight: float,
    rebalance_monthly: bool,
    initial: float = INITIAL_CAPITAL,
    score_start: int = SCORE_START,
) -> list[tuple[int, float, float]]:
    """Panier équipondéré : ``weight`` du capital réparti à parts égales, reste en cash.

    Achat à l'open de la 1ʳᵉ barre ≥ ``score_start``. B0-F : ``weight=1``, jamais rééquilibré.
    B0-E : rééquilibré à l'open de la 1ʳᵉ barre de chaque mois (coûts sur le notionnel échangé).
    Pas de stop. Equity marquée au close. Retourne [(t, equity, exposition brute)].
    """
    symbols = sorted(candles_by_sym)
    idx = {s: {c.time: c for c in candles_by_sym[s]} for s in symbols}
    times = sorted({c.time for s in symbols for c in candles_by_sym[s] if c.time >= score_start})
    cash = initial
    qty = {s: 0.0 for s in symbols}
    last = {s: None for s in symbols}
    cur_month = None
    out: list[tuple[int, float, float]] = []

    def trade_to(s: str, target_notional: float, px: float) -> None:
        nonlocal cash
        c = costs[s]
        cur = qty[s] * px
        delta = target_notional - cur
        if abs(delta) < 1e-9:
            return
        if delta > 0:
            # jamais de cash négatif : l'achat + sa commission tiennent dans le cash (pas de levier)
            delta = min(delta, max(cash, 0.0) / (1 + c.commission_bps / 10_000.0))
            if delta <= 1e-9:
                return
            fill = c.fill(px, "buy")
            q = delta / fill
            fee = c.fee(delta)
            cash -= delta + fee
            qty[s] += q
        else:
            fill = c.fill(px, "sell")
            q = min(qty[s], -delta / px)
            proceeds = q * fill
            cash += proceeds - c.fee(proceeds)
            qty[s] -= q

    for t in times:
        m = _month(t)
        first = cur_month is None
        if first or (rebalance_monthly and m != cur_month):
            if all(t in idx[s] for s in symbols):
                opens = {s: idx[s][t].open for s in symbols}
                eq_open = cash + sum(qty[s] * opens[s] for s in symbols)
                target = eq_open * weight / len(symbols)
                # vendre d'abord, puis acheter (le cash sert aux achats)
                for s in sorted(symbols, key=lambda s: target - qty[s] * opens[s]):
                    trade_to(s, target, opens[s])
                cur_month = m
        for s in symbols:
            if t in idx[s]:
                last[s] = idx[s][t].close
        gross = sum(qty[s] * (last[s] or 0.0) for s in symbols)
        out.append((t, cash + gross, gross))
    return out
