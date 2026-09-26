"""Shared closed-bar filter for cycle API + agent commands (B4 / R2 / P3)."""

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
    """Drop the still-forming bar. Returns (closed, now_s).

    P3 — ``now`` is clamped to wall-clock: never accept a future ``now`` from
    API/agent args (would incorrectly treat the forming bar as closed).
    """
    tf_sec = TF_SECONDS.get(timeframe)
    if tf_sec is None:
        raise ValueError(f"unsupported timeframe: {timeframe}")
    wall = int(time.time())
    now_s = int(now) if now is not None else wall
    now_s = min(now_s, wall)
    closed = closed_candles(list(candles), tf_sec, now_s)
    if not closed:
        raise ValueError("no closed candles available")
    return closed, now_s
