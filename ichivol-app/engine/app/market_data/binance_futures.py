"""Binance USD-M Futures public REST client -- Open Interest + Funding Rate
history only (V2 "participation avancée", docs/METHODS-ROADMAP.md). Public
market data endpoints, no auth, no order/position/account access -- this
engine never touches execution (mission: data != execution, same rule as
every other market_data module here).

Not every spot ticker has an identical futures ticker: Binance renames very
low-unit-price tokens with a "1000" multiplier prefix on futures (confirmed
live 2026-09-16: "PEPEUSDT" comes back an empty `[]`, HTTP 200 -- not an
error -- on both endpoints below, while "1000PEPEUSDT" has real data).
`_FUTURES_SYMBOL` maps the known exceptions; everything else is assumed
identical to its spot ticker and simply comes back empty if that
assumption is wrong for some future listing -- same graceful-degradation
contract as the rest of this module: these functions never raise for "no
futures market for this token", only for a genuine HTTP/network failure.
"""

from __future__ import annotations

from dataclasses import dataclass

import httpx

BASE_URL = "https://fapi.binance.com"

_FUTURES_SYMBOL: dict[str, str] = {
    "PEPEUSDT": "1000PEPEUSDT",
}


def _futures_symbol(spot_symbol: str) -> str:
    return _FUTURES_SYMBOL.get(spot_symbol, spot_symbol)


@dataclass(frozen=True)
class OpenInterestPoint:
    time: int
    open_interest: float


@dataclass(frozen=True)
class FundingPoint:
    time: int
    rate: float


def fetch_open_interest_hist(symbol: str, period: str, limit: int = 500) -> list[OpenInterestPoint]:
    response = httpx.get(
        f"{BASE_URL}/futures/data/openInterestHist",
        params={"symbol": _futures_symbol(symbol), "period": period, "limit": min(max(limit, 1), 500)},
        timeout=15.0,
    )
    response.raise_for_status()
    rows = response.json()
    return [
        OpenInterestPoint(time=int(row["timestamp"]) // 1000, open_interest=float(row["sumOpenInterest"]))
        for row in rows
    ]


def fetch_funding_rate_hist(symbol: str, limit: int = 1000) -> list[FundingPoint]:
    response = httpx.get(
        f"{BASE_URL}/fapi/v1/fundingRate",
        params={"symbol": _futures_symbol(symbol), "limit": min(max(limit, 1), 1000)},
        timeout=15.0,
    )
    response.raise_for_status()
    rows = response.json()
    return [
        FundingPoint(time=int(row["fundingTime"]) // 1000, rate=float(row["fundingRate"]))
        for row in rows
    ]
