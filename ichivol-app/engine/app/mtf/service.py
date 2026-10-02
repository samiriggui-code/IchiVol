"""MTF-1 — collecte des bougies par horizon (I/O) et snapshot pour la route / le screener.

Cache par (provider, symbole, horizon) : une entrée reste valable jusqu'à la **prochaine clôture** de
bougie de l'horizon (au plus ``_MAX_AGE_S`` pour garder la bougie en formation à peu près fraîche). Une
lecture 1d / 1w ne coûte donc qu'un appel par clôture, pas un par scan de 5 min. Les données d'un horizon
dont la clôture est arrivée sont toujours re-téléchargées (pas de faux CONFIRMED sur une bougie périmée).

Jamais appelé par la boucle paper elle-même : le screener calcule la matrice et la boucle se contente de
la recopier dans ``entry_signal`` (observe-only, règle #161).
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any, Sequence

from app.indicators.ichimoku import Candle
from app.market_data.accumulator import fetch_with_accumulation, needs_accumulation
from app.mtf.matrix import HORIZON_SECONDS, MtfMatrix, compute_mtf_matrix, horizons_for

logger = logging.getLogger(__name__)

FETCH_LIMIT = 300
_MAX_AGE_S = 900
# Horizons que chaque provider sait servir. Twelve Data : aucun fetch supplémentaire (budget de crédits,
# même règle que le MTF du pipeline). Biquote n'a pas de 1w.
_PROVIDER_TIMEFRAMES: dict[str, frozenset[str]] = {
    "binance": frozenset({"15m", "1h", "4h", "1d", "1w"}),
    "biquote": frozenset({"15m", "1h", "4h", "1d"}),
    "twelve_data": frozenset(),
}

_lock = threading.Lock()
_cache: dict[tuple[str, str, str], tuple[int, int, list[Candle]]] = {}  # key -> (fetched_at, valid_until, bars)


def clear_cache() -> None:
    with _lock:
        _cache.clear()


def _valid_until(bars: Sequence[Candle], tf_s: int, fetched_at: int) -> int:
    if not bars:
        return fetched_at
    nxt = int(bars[-1].time) + tf_s
    if nxt <= fetched_at:
        # The provider has not delivered the bar that opened at the last boundary yet: retry soon
        # instead of serving a LATE series for up to _MAX_AGE_S.
        return fetched_at + 60
    return min(nxt, fetched_at + _MAX_AGE_S)


def fetch_horizon(provider: Any, symbol: str, provider_symbol: str, timeframe: str, *, now: int) -> list[Candle]:
    key = (provider.id, provider_symbol, timeframe)
    with _lock:
        hit = _cache.get(key)
    if hit is not None and now < hit[1]:
        return hit[2]
    if needs_accumulation(provider.id):
        bars = fetch_with_accumulation(provider, symbol, provider_symbol, timeframe, FETCH_LIMIT)
    else:
        bars = provider.fetch_ohlcv(provider_symbol, timeframe, FETCH_LIMIT)
    bars = list(bars or [])
    with _lock:
        _cache[key] = (now, _valid_until(bars, HORIZON_SECONDS[timeframe], now), bars)
    return bars


def collect_series(
    provider: Any,
    symbol: str,
    provider_symbol: str,
    decision_tf: str,
    *,
    now: int,
    decision_candles: Sequence[Candle] | None = None,
) -> tuple[dict[str, list[Candle] | None], dict[str, str]]:
    """Bougies brutes par horizon + raisons d'indisponibilité. ``decision_candles`` (déjà téléchargées
    par le screener) évitent un second appel pour l'horizon de décision."""
    supported = _PROVIDER_TIMEFRAMES.get(provider.id, frozenset())
    series: dict[str, list[Candle] | None] = {}
    reasons: dict[str, str] = {}
    for tf in horizons_for(decision_tf):
        if tf == decision_tf and decision_candles is not None:
            series[tf] = list(decision_candles)
            continue
        if tf not in supported:
            series[tf] = None
            reasons[tf] = "provider_credit_budget" if provider.id == "twelve_data" else "provider_no_timeframe"
            continue
        try:
            series[tf] = fetch_horizon(provider, symbol, provider_symbol, tf, now=now)
        except Exception:
            logger.warning("mtf: fetch failed for %s %s", provider_symbol, tf, exc_info=True)
            series[tf] = None
            reasons[tf] = "provider_error"
    return series, reasons


def matrix_for_scan(
    provider: Any,
    symbol: str,
    provider_symbol: str,
    decision_tf: str,
    decision_candles: Sequence[Candle],
    *,
    now: int | None = None,
) -> MtfMatrix | None:
    """Matrice calculée pendant un scan du screener. Ne lève jamais : ``None`` en cas d'erreur
    (la matrice est observe-only, elle ne doit pas casser un scan)."""
    try:
        t = int(time.time()) if now is None else int(now)
        series, reasons = collect_series(
            provider, symbol, provider_symbol, decision_tf, now=t, decision_candles=decision_candles
        )
        return compute_mtf_matrix(series, symbol=symbol, decision_tf=decision_tf, now=t, venue=provider.id,
                                  unavailable_reasons=reasons)
    except Exception:
        logger.warning("mtf: matrix failed for %s %s", symbol, decision_tf, exc_info=True)
        return None


def matrix_as_of(symbol: str, decision_tf: str, as_of: int) -> MtfMatrix:
    """Matrice historique : chaque horizon relu tel qu'il était à ``as_of`` (bougies closes à cet instant,
    aucune bougie provisoire : son contenu intrabarre n'est pas reproductible). Limité à la fenêtre
    téléchargée (``FETCH_LIMIT`` bougies) : au-delà, ``insufficient_history``."""
    from app.market_data.resolve import resolve

    resolved = resolve(symbol)
    provider, provider_symbol = resolved.provider, resolved.provider_symbol
    now = int(time.time())
    series, reasons = collect_series(provider, symbol, provider_symbol, decision_tf, now=now)
    return compute_mtf_matrix(series, symbol=symbol, decision_tf=decision_tf, now=int(as_of), venue=provider.id,
                              unavailable_reasons=reasons, include_provisional=False)
