"""Manual one-shot collection pass.

Usage:
    python -m app.market_data.cli BTCUSDT 1h --limit 300

Not a scheduler -- running this periodically (cron, a simple loop, or a
proper task queue) is a separate concern for whichever deployment this
engine ends up in.
"""

from __future__ import annotations

import argparse

from app.db.session import SessionLocal
from app.market_data.collector import upsert_candles
from app.market_data.resolve import resolve


def collect_once(symbol: str, interval: str, limit: int, exchange: str = "binance") -> int:
    provider, provider_symbol = resolve(symbol, default_provider=exchange)
    candles = provider.fetch_ohlcv(provider_symbol, interval, limit)
    # Never persist the last bar: it's almost always still forming, and the
    # (asset, timeframe, timestamp) unique constraint means an inserted row
    # is never updated later with that same bar's final, closed values (see
    # app/market_data/accumulator.py's docstring for the full reasoning).
    closed = candles[:-1]
    session = SessionLocal()
    try:
        return upsert_candles(
            session, symbol=symbol, exchange=provider.id, timeframe=interval, candles=closed
        )
    finally:
        session.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("symbol")
    parser.add_argument("interval")
    parser.add_argument("--limit", type=int, default=300)
    parser.add_argument("--exchange", default="binance")
    args = parser.parse_args()

    inserted = collect_once(args.symbol, args.interval, args.limit, args.exchange)
    print(f"{args.symbol} {args.interval}: {inserted} new candle(s) inserted")


if __name__ == "__main__":
    main()
