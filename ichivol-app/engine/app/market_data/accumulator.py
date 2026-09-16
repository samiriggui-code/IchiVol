"""Backfills a hard-capped live feed with this engine's own accumulated
history, so a live decision or backtest isn't silently starved down to
whatever a single provider call happened to return.

Concrete motivation: biquote (app/market_data/biquote.py) always returns
~100 bars per call regardless of what's asked -- confirmed live,
`/backtest/EURUSD?limit=1000` was quietly served only 99 usable bars, with
nothing in the response to say so. biquote.py's own docstring already names
the intended fix: accumulate depth over time via
app/market_data/collector.py, the same mechanism the manual CLI
(app/market_data/cli.py) already uses -- this module is what wires that
into the *live* request path instead of leaving it a manual-only tool.

Only ever persists CLOSED bars. app/db/models.py's unique constraint on
(asset_id, timeframe, timestamp) is enforced via ON CONFLICT DO NOTHING
(collector.py::upsert_candles) -- an insert never updates an existing row.
A live feed's *last* returned bar is almost always the one still forming;
persisting it once would lock in its incomplete OHLC forever, since no
later call carrying that bar's final, closed values could ever overwrite
it. Dropping the last bar before persisting (while still returning it live,
spliced onto the accumulated history) avoids that trap entirely.
"""

from __future__ import annotations

from typing import Sequence

from app.db.session import SessionLocal
from app.indicators.ichimoku import Candle
from app.market_data.collector import fetch_stored_candles, upsert_candles
from app.market_data.provider import MarketDataProvider

# binance and twelve_data already serve the full requested depth (up to
# their own real ceilings) in a single call -- routing them through DB
# accumulation too would only add write/read round-trips to an already-hot
# path (the screener scans 20 symbols every 5 minutes) for zero benefit.
# biquote is the one provider whose cap is far below what callers actually
# ask for.
_HARD_CAPPED_PROVIDERS = {"biquote"}


def needs_accumulation(provider_id: str) -> bool:
    return provider_id in _HARD_CAPPED_PROVIDERS


def _merge(stored: Sequence[Candle], live: Sequence[Candle]) -> list[Candle]:
    """Stored (older, closed) history plus every bar the live call actually
    returned -- live always wins on any timestamp overlap, since it is the
    freshest read and is the only side that ever carries the still-forming
    last bar."""
    if not live:
        return list(stored)
    live_start = live[0].time
    merged = [c for c in stored if c.time < live_start] + list(live)
    merged.sort(key=lambda c: c.time)
    return merged


def fetch_with_accumulation(
    provider: MarketDataProvider,
    symbol: str,
    provider_symbol: str,
    timeframe: str,
    limit: int,
) -> list[Candle]:
    """`symbol` is the stable catalog id (what the rest of the engine keys
    history by -- same convention app/market_data/cli.py already uses), NOT
    `provider_symbol` (the provider's own native ticker, which can differ,
    e.g. catalog "SPX" -> biquote "US500")."""
    live = provider.fetch_ohlcv(provider_symbol, timeframe, limit)
    if not live:
        return live

    closed = live[:-1]  # never persist the still-forming last bar

    session = SessionLocal()
    try:
        if closed:
            upsert_candles(
                session, symbol=symbol, exchange=provider.id, timeframe=timeframe, candles=closed
            )
        stored = fetch_stored_candles(
            session, symbol=symbol, exchange=provider.id, timeframe=timeframe, limit=limit
        )
    finally:
        session.close()

    merged = _merge(stored, live)
    # Accumulated history can exceed what was asked for once enough calls
    # have built up depth -- trim to the requested window, keeping the most
    # recent bars (never drop the live tail).
    return merged[-limit:] if len(merged) > limit else merged
