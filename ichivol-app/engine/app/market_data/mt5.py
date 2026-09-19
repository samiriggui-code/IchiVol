"""MT5Provider -- HTTP client to the mt5-bridge service (Phase 2, READ ONLY).

The official `MetaTrader5` python package only runs alongside a real MT5
terminal on Windows (or Wine); it cannot be imported from this engine's own
Linux container. So the actual terminal/broker connection lives in a
separate service, `ichivol-app/mt5-bridge/` (Wine + MT5 terminal + a thin
FastAPI wrapper), reachable only on its own isolated Docker network --
never on the `ichivol` network, never on a public port (docs/
TRADING_ARCHITECTURE_V2.md §11: MT5 is a data source/lab, not a dependency
the core engine needs to boot).

This module is the Linux side of that seam: a plain httpx client, same
shape as app/market_data/biquote.py and app/market_data/twelve_data.py, so
the rest of the engine (registry, resolve, screener, backtest) never has to
know MT5 exists behind it. Unregistered by default (see
app/market_data/registry.py) -- setting MT5_ENABLED=true is the only thing
that makes `get_provider("mt5")` return anything.

Symbol aliasing (XAUUSD vs XAUUSD.a vs XAUUSDm), timeframe enum mapping
(M15/H1/H4/D1), and the actual broker login/connection state all live on
the bridge side, which talks to the live terminal and therefore is the only
place that can resolve them correctly for whichever broker is configured.
This client sends the *canonical* IchiVol symbol/timeframe strings
(identical convention to every other provider) and trusts the bridge's
response to say what it actually used.
"""

from __future__ import annotations

import httpx

from app.config import settings
from app.indicators.ichimoku import Candle
from app.market_data.volume_semantics import VolumeType

_SUPPORTED_TIMEFRAMES = {"15m", "1h", "4h", "1d"}

_BRIDGE_VOLUME_TYPE: dict[str, VolumeType] = {
    "real": VolumeType.REPORTED_VOLUME,
    "tick": VolumeType.TICK_VOLUME,
}


class MT5ConnectionError(RuntimeError):
    """Bridge unreachable, or reachable but not connected to the broker/terminal."""


def _volume_type_from_bridge(raw: str | None) -> VolumeType:
    if not raw:
        return VolumeType.NONE
    return _BRIDGE_VOLUME_TYPE.get(raw.strip().lower(), VolumeType.NONE)


def fetch_ohlcv(provider_symbol: str, timeframe: str, limit: int = 300) -> list[Candle]:
    if timeframe not in _SUPPORTED_TIMEFRAMES:
        raise ValueError(f"unsupported timeframe for mt5: {timeframe!r}")

    try:
        response = httpx.get(
            f"{settings.mt5_bridge_url}/ohlcv",
            params={"symbol": provider_symbol, "timeframe": timeframe, "limit": limit},
            timeout=settings.mt5_timeout_s,
        )
    except httpx.TimeoutException as exc:
        raise MT5ConnectionError(f"mt5_bridge_timeout: {provider_symbol!r} {timeframe}") from exc
    except httpx.TransportError as exc:
        raise MT5ConnectionError(f"mt5_bridge_unreachable: {exc}") from exc

    if response.status_code == 503:
        # Bridge is up but the terminal isn't logged into the broker (or the
        # broker connection dropped) -- distinct from a network failure so
        # callers/observability can tell "MT5 off" from "MT5 misbehaving".
        raise MT5ConnectionError(f"mt5_not_connected: {response.text}")

    try:
        body = response.json()
    except ValueError:
        response.raise_for_status()
        raise

    if isinstance(body, dict) and "bars" not in body and "error" in body:
        raise ValueError(f"mt5_error: {body['error']}")

    response.raise_for_status()

    bars = body.get("bars") if isinstance(body, dict) else None
    if not bars:
        raise ValueError(f"mt5_empty: no bars for {provider_symbol!r} {timeframe}")

    volume_type = _volume_type_from_bridge(body.get("volume_type"))

    candles = [
        Candle(
            time=int(bar["time"]),
            open=float(bar["open"]),
            high=float(bar["high"]),
            low=float(bar["low"]),
            close=float(bar["close"]),
            volume=float(bar.get("volume") or 0.0),
            volume_type=volume_type,
        )
        for bar in bars
    ]

    # Never trust the bridge's ordering, and never let a broken feed hand
    # back duplicate timestamps (a reconnect / partial retry on the bridge
    # side is the realistic cause) -- last write wins, oldest-first output,
    # same normalization discipline as every other provider.
    by_time: dict[int, Candle] = {}
    for c in candles:
        by_time[c.time] = c
    return [by_time[t] for t in sorted(by_time)]


class MT5Provider:
    id = "mt5"
    volume_type = VolumeType.TICK_VOLUME  # provider-level default; per-candle can differ

    def fetch_ohlcv(self, provider_symbol: str, timeframe: str, limit: int = 300) -> list[Candle]:
        return fetch_ohlcv(provider_symbol, timeframe, limit)
