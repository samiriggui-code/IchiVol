"""AG0: calculate_ichimoku / calculate_rvol must drop the still-forming bar."""

from __future__ import annotations

import time

import pytest

from app.agent_channel import commands as cmds
from app.config import settings
from app.indicators.ichimoku import Candle
from app.screener.service import _closed_only
from tests.indicators.test_ichimoku_lookahead import _make_candles


def _with_forming_tail(n: int = 80) -> tuple[list[Candle], list[Candle]]:
    """Historical closed bars + one still-forming bar (open ≈ now)."""
    now = int(time.time())
    tf = 3600
    base = _make_candles(n, seed=11)
    closed: list[Candle] = []
    for i, c in enumerate(base):
        t = now - (n - i) * tf
        closed.append(
            Candle(
                time=t,
                open=c.open,
                high=c.high,
                low=c.low,
                close=c.close,
                volume=c.volume,
                volume_type=c.volume_type,
            )
        )
    last = closed[-1]
    forming = Candle(
        time=now - 120,  # opened 2 min ago → not closed for 1h
        open=last.close * 1.5,
        high=last.close * 1.6,
        low=last.close * 1.4,
        close=last.close * 1.55,
        volume=9999.0,
        volume_type=last.volume_type,
    )
    return closed, closed + [forming]


def test_closed_only_drops_forming_bar():
    closed, with_forming = _with_forming_tail()
    assert len(_closed_only(with_forming, "1h")) == len(closed)
    assert _closed_only(with_forming, "1h")[-1].time == closed[-1].time


@pytest.mark.parametrize("cmd", [cmds.cmd_calculate_ichimoku, cmds.cmd_calculate_rvol])
def test_calculate_commands_ignore_forming_bar(cmd, monkeypatch):
    monkeypatch.setattr(settings, "decide_on_closed_candles", True)
    closed_only, series = _with_forming_tail()

    class _P:
        id = "binance"

    monkeypatch.setattr(
        cmds,
        "resolve_and_fetch",
        lambda s, tf, lim: (_P(), s, list(series)),
    )
    with_forming = cmd({"symbol": "BTCUSDT", "timeframe": "1h", "limit": 300})

    monkeypatch.setattr(
        cmds,
        "resolve_and_fetch",
        lambda s, tf, lim: (_P(), s, list(closed_only)),
    )
    without = cmd({"symbol": "BTCUSDT", "timeframe": "1h", "limit": 300})

    # Same closed series → identical indicator payload (forming bar must be dropped).
    assert with_forming == without
