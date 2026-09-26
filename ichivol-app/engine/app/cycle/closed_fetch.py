"""Shared closed-bar filter for cycle API + agent commands (B4 / R2)."""

from __future__ import annotations

import time
from typing import Sequence

from app.indicators.ichimoku import Candle
from app.market_data.quality import closed_candles
from app.market_data.timeframes import TF_SECONDS


def filter_closed_candles(
    candles: Sequence[Candle],
    timeframe: str,
    *,
    now: int | None = None,
) -> tuple[list[Candle], int]:
    """Drop the still-forming bar. Returns (closed, now_s)."""
    tf_sec = TF_SECONDS.get(timeframe)
    if tf_sec is None:
        raise ValueError(f"unsupported timeframe: {timeframe}")
    now_s = int(now) if now is not None else int(time.time())
    closed = closed_candles(list(candles), tf_sec, now_s)
    if not closed:
        raise ValueError("no closed candles available")
    return closed, now_s
