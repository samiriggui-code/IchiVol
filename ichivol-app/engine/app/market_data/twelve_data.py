"""Twelve Data OHLCV adapter (Phase 1b multi-actifs, equities only since
Phase 1c -- see app/universe/catalog.py).

Free Basic plan ≈ 8 API credits / minute. This module:
- serializes outbound calls
- rate-limits to ``_MAX_CREDITS_PER_MIN`` (leave headroom)
- caches series ~55s so chart + decision + retries share one credit

Requires ``TWELVE_DATA_API_KEY`` in engine ``.env`` as the operator-wide
fallback. A logged-in user with their own key (Settings -> Marché on the
frontend) gets it forwarded as the `X-Twelve-Data-Key` header by
server/src/engine/proxy.ts; app/api/routes.py reads that header and calls
`set_api_key_override()` before touching this module, so their requests use
their own quota instead of the shared one. The override is a plain
`ContextVar`, not a parameter threaded through `MarketDataProvider` --
Starlette/anyio copy the context fresh for each request's threadpool run
(see `run_in_threadpool`), so a `.set()` here never leaks between requests;
it just has to happen in the same request's own call stack, which is what
routes.py does.
"""

from __future__ import annotations

import logging
import threading
import time
from contextvars import ContextVar
from datetime import datetime, timezone

import httpx

from app.config import settings
from app.indicators.ichimoku import Candle

logger = logging.getLogger(__name__)

_api_key_override: ContextVar[str | None] = ContextVar("twelve_data_api_key_override", default=None)


def set_api_key_override(key: str | None) -> None:
    _api_key_override.set(key or None)


def _resolve_api_key() -> str:
    return (_api_key_override.get() or settings.twelve_data_api_key).strip()

BASE_URL = "https://api.twelvedata.com"

_INTERVAL: dict[str, str] = {
    "15m": "15min",
    "1h": "1h",
    "4h": "4h",
    "1d": "1day",
}

# Leave 1 credit headroom vs the public "8 / min" Basic cap.
_MAX_CREDITS_PER_MIN = 7
_CACHE_TTL_SEC = 90.0

_cache: dict[tuple[str, str], tuple[float, list[Candle]]] = {}
_credit_times: list[float] = []
_lock = threading.Lock()


def _parse_time(value: str) -> int:
    raw = value.strip()
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(raw, fmt).replace(tzinfo=timezone.utc)
            return int(dt.timestamp())
        except ValueError:
            continue
    dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp())


def _credits_hint(message: str) -> str:
    lower = message.lower()
    if "credit" in lower or "rate" in lower or "limit" in lower:
        return (
            f"{message} "
            "(Basic ≈8/min — le moteur queue + cache; attends ou réduis les changements de symbole)"
        )
    return message


def _wait_for_credit_slot() -> None:
    """Block until a credit is available under the per-minute budget."""
    while True:
        with _lock:
            now = time.monotonic()
            # drop timestamps older than 60s
            alive = [t for t in _credit_times if now - t < 60.0]
            _credit_times.clear()
            _credit_times.extend(alive)
            if len(_credit_times) < _MAX_CREDITS_PER_MIN:
                _credit_times.append(now)
                return
            sleep_for = 60.0 - (now - _credit_times[0]) + 0.15
        logger.info("twelve_data: rate limit pause %.1fs", sleep_for)
        time.sleep(max(sleep_for, 0.2))


def fetch_time_series(provider_symbol: str, timeframe: str, limit: int = 300) -> list[Candle]:
    api_key = _resolve_api_key()
    if not api_key:
        raise ValueError(
            "twelve_data_api_key_missing: set TWELVE_DATA_API_KEY in engine/.env, "
            "or the client can set their own key in Settings -> Marché"
        )

    interval = _INTERVAL.get(timeframe)
    if interval is None:
        raise ValueError(f"unsupported timeframe for twelve_data: {timeframe!r}")

    # One cache entry per symbol+TF; always pull enough bars for chart+indicators.
    want = min(max(limit, 300), 5000)
    cache_key = (provider_symbol, timeframe)

    with _lock:
        hit = _cache.get(cache_key)
        if hit is not None and time.monotonic() - hit[0] < _CACHE_TTL_SEC:
            cached = hit[1]
            if len(cached) >= min(want, len(cached)):
                return list(cached[-want:] if len(cached) > want else cached)

    _wait_for_credit_slot()

    response = httpx.get(
        f"{BASE_URL}/time_series",
        params={
            "symbol": provider_symbol,
            "interval": interval,
            "outputsize": want,
            "apikey": api_key,
            "timezone": "UTC",
            "order": "ASC",
        },
        timeout=25.0,
    )
    try:
        body = response.json()
    except ValueError:
        response.raise_for_status()
        raise

    if isinstance(body, dict) and body.get("status") == "error":
        raise ValueError(f"twelve_data_error: {_credits_hint(str(body.get('message') or body))}")

    response.raise_for_status()

    values = body.get("values") if isinstance(body, dict) else None
    if not values:
        raise ValueError(f"twelve_data_empty: no values for {provider_symbol!r} {timeframe}")

    candles: list[Candle] = []
    for row in values:
        vol_raw = row.get("volume")
        volume = float(vol_raw) if vol_raw not in (None, "", "null") else 0.0
        candles.append(
            Candle(
                time=_parse_time(str(row["datetime"])),
                open=float(row["open"]),
                high=float(row["high"]),
                low=float(row["low"]),
                close=float(row["close"]),
                volume=volume,
            )
        )

    with _lock:
        _cache[cache_key] = (time.monotonic(), list(candles))
    return candles


class TwelveDataProvider:
    id = "twelve_data"

    def fetch_ohlcv(self, provider_symbol: str, timeframe: str, limit: int = 300) -> list[Candle]:
        return fetch_time_series(provider_symbol, timeframe, limit)
