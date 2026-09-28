"""RS-D1 — cassure Donchian 55 / stop suiveur 3 ATR / sortie canal 20, portefeuille à capital commun.

Implémentation normative de docs/RS-03-DONCHIAN-4H-SPEC.md. Les règles vivent dans ``rs/book.py``
(``Book``, seule implémentation, partagée avec le paper live, RS-09 §1) ; ``simulate`` n'est que la
boucle de backtest sur les barres.
Causal par construction : à la clôture de la barre ``t``, seules les barres ``<= t`` sont lues ;
les indicateurs viennent de ``app/indicators`` (Donchian exclut la barre signal, ATR = moyenne simple).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Sequence

from app.indicators.ichimoku import Candle

from rs import DATA_END_EXCL, INITIAL_CAPITAL, SCORE_START, SEED
from rs.book import Book, Trade, _Pos, day_key, size_entry
from rs.costs import SymbolCost
from rs.data import assert_no_reserved

__all__ = ["RunOutput", "Trade", "_Pos", "simulate", "size_entry"]

_day = day_key  # compat


@dataclass
class RunOutput:
    trades: list[Trade]
    equity: list[tuple[int, float, float]]  # (bar_open_time, equity marquée au close, exposition brute)
    stop_log: dict[str, list[tuple[int, float]]]  # symbole -> [(barre, stop applicable à la barre suivante)]
    orders: list[tuple[int, str, str]]  # (barre de décision, symbole, "entry"|"exit")
    rejections: dict[str, int] = field(default_factory=dict)
    halt_days: int = 0


def simulate(
    candles_by_sym: dict[str, Sequence[Candle]],
    costs: dict[str, SymbolCost],
    *,
    initial: float = INITIAL_CAPITAL,
    score_start: int = SCORE_START,
    exec_delay: int = 1,
    seed: int = SEED,
    data_end_excl: int = DATA_END_EXCL,
) -> RunOutput:
    """``exec_delay`` = barres entre la décision et l'exécution (1 = open t+1 ; 2 = stress §9)."""
    for s in candles_by_sym:
        assert_no_reserved(list(candles_by_sym[s]), data_end_excl)
    book = Book(candles_by_sym, costs, initial=initial, score_start=score_start, exec_delay=exec_delay, seed=seed)
    times = sorted({c.time for s in book.symbols for c in book.bars[s]})
    for t in times:
        book.step(t)
    book.finalize()
    return RunOutput(book.trades, book.equity, book.stop_log, book.orders, book.rej, book.halt_days)
