"""Robust mark resolution for paper valuation (T0-BROKER).

Prefer the in-memory screener cache; if a symbol is missing (engine restart,
symbol outside the screener universe), fall back to the last candle via
``resolve_and_fetch`` (uses the existing provider candle cache).

Overview path: never block on Twelve Data credit waits — use a wall-clock
budget and non-blocking credit acquisition; symbols still missing become
``source="missing"``.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Iterable

from app.market_data.timeframes import TF_SECONDS
from app.screener.cache import screener_cache

logger = logging.getLogger(__name__)

# Overview must stay snappy even when Twelve Data credits are exhausted.
OVERVIEW_FETCH_BUDGET_S = 2.0


@dataclass(frozen=True)
class Mark:
    price: float
    as_of: float  # unix epoch seconds
    source: str  # "screener_cache" | "candle" | "missing"


def peek_screener_marks() -> dict[str, tuple[float, float]]:
    """symbol -> (price, computed_at epoch). Read-only cache peek."""
    marks: dict[str, tuple[float, float]] = {}
    for tf in ("1h", "4h", "15m", "1d"):
        entry = screener_cache.get(tf)
        if entry is None:
            continue
        for row in entry.rows:
            marks.setdefault(row.symbol, (row.price, entry.computed_at))
    return marks


def mark_stale(mark: Mark | None, timeframe: str, *, now: float | None = None) -> bool:
    """True when the mark is older than two bars of the position timeframe."""
    if mark is None or mark.source == "missing":
        return True
    now = now if now is not None else time.time()
    tf_s = float(TF_SECONDS.get(timeframe, 3600))
    return (now - float(mark.as_of)) > 2.0 * tf_s


def resolve_marks(
    symbols: Iterable[str],
    *,
    timeframe: str = "1h",
    allow_fetch: bool = True,
    fetch_budget_s: float | None = None,
    block_on_provider: bool = True,
) -> dict[str, Mark]:
    """Return a Mark per requested symbol (missing source when unavailable).

    ``fetch_budget_s``: wall-clock cap for all candle fallbacks (None = no cap).
    ``block_on_provider``: if False, Twelve Data must not wait for credits —
    skip network when the rate limiter would sleep.
    """
    wanted = {s.upper() for s in symbols}
    out: dict[str, Mark] = {}
    cached = peek_screener_marks()
    for sym in wanted:
        hit = None
        for k, v in cached.items():
            if k.upper() == sym:
                hit = v
                break
        if hit is not None:
            out[sym] = Mark(price=float(hit[0]), as_of=float(hit[1]), source="screener_cache")

    missing = wanted - set(out)
    if not missing or not allow_fetch:
        for sym in missing:
            out[sym] = Mark(price=0.0, as_of=0.0, source="missing")
        return out

    from app.market_data.resolve import resolve_and_fetch

    deadline = None if fetch_budget_s is None else time.monotonic() + float(fetch_budget_s)
    # Non-blocking path: monkeypatch Twelve Data credit wait to a try-acquire.
    _credit_patch = None
    if not block_on_provider:
        try:
            from app.market_data import twelve_data as td

            def _no_wait():
                if not td._try_acquire_credit_slot():
                    raise TimeoutError("twelve_data_credit_unavailable")

            _credit_patch = td
            _orig_wait = td._wait_for_credit_slot
            td._wait_for_credit_slot = _no_wait  # type: ignore[method-assign]
        except Exception:  # noqa: BLE001
            _credit_patch = None
            _orig_wait = None

    try:
        for sym in sorted(missing):
            if deadline is not None and time.monotonic() >= deadline:
                out[sym] = Mark(price=0.0, as_of=0.0, source="missing")
                continue
            try:
                _prov, _psym, candles = resolve_and_fetch(sym, timeframe, 5)
            except Exception as exc:  # noqa: BLE001 — provider/network/credit; leave missing
                logger.debug("mark fetch failed for %s: %s", sym, exc)
                out[sym] = Mark(price=0.0, as_of=0.0, source="missing")
                continue
            if not candles:
                out[sym] = Mark(price=0.0, as_of=0.0, source="missing")
                continue
            last = candles[-1]
            out[sym] = Mark(price=float(last.close), as_of=float(last.time), source="candle")
    finally:
        if _credit_patch is not None and _orig_wait is not None:
            _credit_patch._wait_for_credit_slot = _orig_wait  # type: ignore[method-assign]

    for sym in missing:
        out.setdefault(sym, Mark(price=0.0, as_of=0.0, source="missing"))
    return out
