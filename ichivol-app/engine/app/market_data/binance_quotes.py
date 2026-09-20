"""Binance public bid/ask and trades (data-only; no account, no orders).

Endpoints confirmed live 2026-09-20: ``/api/v3/ticker/bookTicker`` (best
bid/ask + sizes), ``/api/v3/trades`` (recent trades, ``isBuyerMaker``).
Binance does not label the feed delayed; ``delayed`` stays ``None`` (unknown)
rather than being assumed real-time -- receipt time is recorded for staleness
checks by the caller.
"""

from __future__ import annotations

from datetime import datetime, timezone

import httpx

from app.market_data.binance import BASE_URL
from app.market_data.contracts import Provenance, Quote, Trade


def _now() -> datetime:
    return datetime.now(timezone.utc)


def parse_book_ticker(instrument_id: str, body: dict, received_at: datetime) -> Quote:
    """bookTicker carries no exchange timestamp: market_time is unknown, so the
    receipt time is used and the transform is labelled accordingly."""
    return Quote(
        instrument_id=instrument_id,
        bid=float(body["bidPrice"]),
        ask=float(body["askPrice"]),
        bid_size=float(body["bidQty"]),
        ask_size=float(body["askQty"]),
        provenance=Provenance(
            source="binance",
            market_time=received_at,
            received_at=received_at,
            delayed=None,
            transforms=("market_time=received_at (bookTicker has no timestamp)",),
        ),
    )


def parse_trades(instrument_id: str, rows: list[dict], received_at: datetime) -> list[Trade]:
    return [
        Trade(
            instrument_id=instrument_id,
            price=float(r["price"]),
            size=float(r["qty"]),
            buyer_is_aggressor=not bool(r["isBuyerMaker"]),
            provenance=Provenance(
                source="binance",
                market_time=datetime.fromtimestamp(int(r["time"]) / 1000, tz=timezone.utc),
                received_at=received_at,
                delayed=None,
            ),
        )
        for r in rows
    ]


class BinanceQuoteProvider:
    id = "binance"

    def fetch_quote(self, provider_symbol: str) -> Quote:
        r = httpx.get(f"{BASE_URL}/api/v3/ticker/bookTicker", params={"symbol": provider_symbol}, timeout=10.0)
        r.raise_for_status()
        return parse_book_ticker(provider_symbol, r.json(), _now())

    def fetch_trades(self, provider_symbol: str, limit: int = 100) -> list[Trade]:
        r = httpx.get(f"{BASE_URL}/api/v3/trades", params={"symbol": provider_symbol, "limit": limit}, timeout=10.0)
        r.raise_for_status()
        return parse_trades(provider_symbol, r.json(), _now())
