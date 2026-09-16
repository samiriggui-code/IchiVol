"""biquote.io OHLCV adapter -- FX / metals / indices / energy (Phase 1c).

Free, keyless REST API backed by MetaTrader-5 CFD mirrors. Endpoints
confirmed live by hand (2026-09-15):

    GET https://biquote.io/api/{SYMBOL}/ohlc?interval={tf}&count={n}

``interval`` accepts the same strings the engine already uses elsewhere
(``15m``, ``1h``, ``4h``, ``1d``) -- no remapping table needed, unlike
Twelve Data. No API key, no documented per-minute quota.

One real constraint found by probing ``count`` up to 1000: the server
always caps the response at ``_MAX_BARS_PER_CALL`` bars regardless of what
was asked for. So this is a *live feed*, not a one-shot historical
backfill source -- depth builds up the same way any live-only feed would,
through repeated calls persisted by `app/market_data/collector.py`
(`upsert_candles` is idempotent, so polling this on a schedule is exactly
how 500+ bars of history accumulate over time).

``volume`` is always 0 here (CFD mirrors carry no real exchange tape) --
``tickVolume`` (count of price updates) is the only participation proxy
biquote gives us, same caveat as Twelve Data's own forex feed collapsing
to 0. Equities (AAPL, TSLA) stay on Twelve Data for real exchange volume;
this adapter is for asset classes where no provider has real volume
anyway (forex/metal/index/energy), so switching away from Twelve Data's
flat 0 to a live tickVolume proxy is a pure upgrade, not a trade-off.
"""

from __future__ import annotations

import threading
import time
from datetime import datetime, timezone

import httpx

from app.indicators.ichimoku import Candle

BASE_URL = "https://biquote.io/api"

_SUPPORTED_TIMEFRAMES = {"15m", "1h", "4h", "1d"}

# Live-confirmed: requesting count=1000 still returns 101 bars.
_MAX_BARS_PER_CALL = 100

_CACHE_TTL_SEC = 30.0
_cache: dict[tuple[str, str], tuple[float, list[Candle]]] = {}
_lock = threading.Lock()


def _parse_iso(value: str) -> int:
    dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp())


def fetch_ohlc(provider_symbol: str, timeframe: str, limit: int = 300) -> list[Candle]:
    if timeframe not in _SUPPORTED_TIMEFRAMES:
        raise ValueError(f"unsupported timeframe for biquote: {timeframe!r}")

    want = min(max(limit, 1), _MAX_BARS_PER_CALL)
    cache_key = (provider_symbol, timeframe)

    with _lock:
        hit = _cache.get(cache_key)
        if hit is not None and time.monotonic() - hit[0] < _CACHE_TTL_SEC:
            cached = hit[1]
            if len(cached) >= min(want, len(cached)):
                return list(cached[-want:] if len(cached) > want else cached)

    response = httpx.get(
        f"{BASE_URL}/{provider_symbol}/ohlc",
        params={"interval": timeframe, "count": want},
        timeout=15.0,
    )
    try:
        body = response.json()
    except ValueError:
        response.raise_for_status()
        raise

    if isinstance(body, dict) and "bars" not in body and "message" in body:
        raise ValueError(f"biquote_error: {body['message']}")

    response.raise_for_status()

    bars = body.get("bars") if isinstance(body, dict) else None
    if not bars:
        raise ValueError(f"biquote_empty: no bars for {provider_symbol!r} {timeframe}")

    candles = [
        Candle(
            time=_parse_iso(str(bar["openTime"])),
            open=float(bar["open"]),
            high=float(bar["high"]),
            low=float(bar["low"]),
            close=float(bar["close"]),
            volume=float(bar.get("tickVolume") or 0.0),
        )
        for bar in bars
    ]
    candles.sort(key=lambda c: c.time)  # biquote returns newest-first

    with _lock:
        _cache[cache_key] = (time.monotonic(), list(candles))
    return candles


class BiquoteProvider:
    id = "biquote"

    def fetch_ohlcv(self, provider_symbol: str, timeframe: str, limit: int = 300) -> list[Candle]:
        return fetch_ohlc(provider_symbol, timeframe, limit)
