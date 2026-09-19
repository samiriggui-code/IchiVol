"""mt5-bridge -- the only piece of IchiVol allowed to import an MT5 client.

Runs as native Linux Python (this file itself needs no Wine) and talks to
the MetaTrader5 terminal, which DOES run under Wine in the same container,
through `mt5linux` (github.com/lucas-campagna/mt5linux): a small RPyC server
runs inside Wine's own Python (started by docker-entrypoint.sh alongside the
terminal), and `mt5linux.MetaTrader5` here is a pure-python client to it --
same method names as the official `MetaTrader5` package
(login/copy_rates_from_pos/symbol_info/...), so this module reads like it
was written against the real package.

Exposes exactly what app/market_data/mt5.py (the Linux engine's client)
needs -- nothing else. No order placement endpoints exist yet (READ ONLY,
docs/TRADING_ARCHITECTURE_V2.md MT5 phase plan: paper/demo execution is a
separate, later, explicitly-approved phase).

NOTE: written against `mt5linux`'s and `MetaTrader5`'s documented APIs but
not exercised against a live terminal in this environment (no Windows/Wine
sandbox available here) -- treat first deploy as a smoke test, not a known-
working artifact. See README.md "Verification checklist".
"""

from __future__ import annotations

import logging
import os
import threading
import time
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse

from symbol_map import SymbolNotFoundError, resolve_symbol

logger = logging.getLogger("mt5_bridge")
logging.basicConfig(level=logging.INFO)

app = FastAPI(title="ichivol-mt5-bridge", version="0.1.0")

_TIMEFRAME_MAP_NAMES = {
    "15m": "TIMEFRAME_M15",
    "1h": "TIMEFRAME_H1",
    "4h": "TIMEFRAME_H4",
    "1d": "TIMEFRAME_D1",
}

_WINE_HOST = os.environ.get("MT5LINUX_HOST", "127.0.0.1")
_WINE_PORT = int(os.environ.get("MT5LINUX_PORT", "18812"))
_MT5_LOGIN = os.environ.get("MT5_LOGIN")
_MT5_PASSWORD = os.environ.get("MT5_PASSWORD")
_MT5_SERVER = os.environ.get("MT5_SERVER")

_lock = threading.Lock()
_client = None  # lazily-connected mt5linux client
_connected_since: float | None = None


def _connect_locked():
    """Must be called with `_lock` held. Raises on any failure -- callers
    turn that into a 503 so the engine-side client can tell "bridge up but
    not connected" apart from "bridge unreachable" (app/market_data/mt5.py)."""
    global _client, _connected_since
    from mt5linux import MetaTrader5  # imported lazily: unavailable outside this container

    client = MetaTrader5(host=_WINE_HOST, port=_WINE_PORT)
    if not client.initialize():
        raise RuntimeError(f"mt5_initialize_failed: {client.last_error()}")
    if _MT5_LOGIN and _MT5_PASSWORD and _MT5_SERVER:
        ok = client.login(int(_MT5_LOGIN), password=_MT5_PASSWORD, server=_MT5_SERVER)
        if not ok:
            raise RuntimeError(f"mt5_login_failed: {client.last_error()}")
    _client = client
    _connected_since = time.monotonic()


def _get_client():
    with _lock:
        if _client is not None:
            return _client
        _connect_locked()
        return _client


@app.get("/health")
def health() -> JSONResponse:
    try:
        client = _get_client()
        account = client.account_info()
        return JSONResponse(
            {
                "connected": True,
                "broker": getattr(account, "company", None) if account else None,
                "server": getattr(account, "server", None) if account else None,
                "login": getattr(account, "login", None) if account else None,
                "uptime_s": (time.monotonic() - _connected_since) if _connected_since else None,
            }
        )
    except Exception as exc:  # noqa: BLE001 -- health check must never 500-crash-loop callers
        logger.warning("mt5_bridge health check failed: %s", exc)
        return JSONResponse({"connected": False, "error": str(exc)}, status_code=503)


@app.get("/ohlcv")
def ohlcv(
    symbol: str = Query(...),
    timeframe: str = Query(...),
    limit: int = Query(300, ge=1, le=5000),
):
    tf_name = _TIMEFRAME_MAP_NAMES.get(timeframe)
    if tf_name is None:
        raise HTTPException(400, f"unsupported timeframe for mt5-bridge: {timeframe!r}")

    try:
        client = _get_client()
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(503, f"mt5_not_connected: {exc}") from exc

    try:
        resolved_symbol = resolve_symbol(client, symbol)
    except SymbolNotFoundError as exc:
        raise HTTPException(422, str(exc)) from exc

    tf_const = getattr(client, tf_name)
    rates = client.copy_rates_from_pos(resolved_symbol, tf_const, 0, limit)
    if rates is None or len(rates) == 0:
        return {"symbol": symbol, "resolved_symbol": resolved_symbol, "bars": [], "volume_type": "tick"}

    # `real_volume` is 0 for almost every FX/CFD symbol (broker doesn't
    # report it) but genuinely populated for some futures feeds -- decide
    # tick vs real from what THIS symbol's rows actually carry, never assume
    # broker-wide (docs/TRADING_ARCHITECTURE_V2.md volume semantics rule).
    any_real_volume = any(float(row["real_volume"]) > 0 for row in rates)
    volume_type = "real" if any_real_volume else "tick"

    bars = [
        {
            "time": int(row["time"]),
            "open": float(row["open"]),
            "high": float(row["high"]),
            "low": float(row["low"]),
            "close": float(row["close"]),
            "volume": float(row["real_volume"]) if any_real_volume else float(row["tick_volume"]),
        }
        for row in rates
    ]

    return {
        "symbol": symbol,
        "resolved_symbol": resolved_symbol,
        "timeframe": timeframe,
        "volume_type": volume_type,
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "bars": bars,
    }
