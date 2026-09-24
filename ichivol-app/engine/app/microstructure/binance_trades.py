"""Binance aggTrades fetch with aggressor side — research / Lab only."""

from __future__ import annotations

from typing import Any

import httpx

from app.market_data.binance import BASE_URL
from app.microstructure.trade_cvd import AggressorTrade


def fetch_binance_agg_trades(
    provider_symbol: str,
    start_ms: int,
    end_ms: int,
    *,
    max_pages: int = 20,
) -> list[AggressorTrade]:
    """Paginated aggTrades in ``[start_ms, end_ms)`` with aggressor side.

    ``m`` = buyer is maker → aggressor is seller when True.
    """
    out: list[AggressorTrade] = []
    params: dict[str, Any] = {
        "symbol": provider_symbol,
        "startTime": start_ms,
        "endTime": end_ms - 1,
        "limit": 1000,
    }
    for _ in range(max_pages):
        r = httpx.get(f"{BASE_URL}/api/v3/aggTrades", params=params, timeout=20.0)
        r.raise_for_status()
        rows = r.json()
        if not rows:
            break
        for x in rows:
            t = int(x["T"])
            if not (start_ms <= t < end_ms):
                continue
            out.append(
                AggressorTrade(
                    time_ms=t,
                    price=float(x["p"]),
                    size=float(x["q"]),
                    buyer_is_aggressor=not bool(x["m"]),
                )
            )
        if len(rows) < 1000 or int(rows[-1]["T"]) >= end_ms - 1:
            break
        params = {"symbol": provider_symbol, "fromId": int(rows[-1]["a"]) + 1, "limit": 1000}
    return out
