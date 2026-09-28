"""Helpers for RS-D1 paper tests (docs/RS-09-RS-D1-PAPER-DESIGN.md)."""

from __future__ import annotations

import bisect
import uuid
from copy import deepcopy
from datetime import datetime, timezone
from typing import Sequence

from app.db.models import PaperPortfolio
from app.indicators.ichimoku import Candle
from app.paper.strategy_profiles import RS_D1_PROFILE
from rs import BAR_SECONDS


class FakeSource:
    """Closed 4h bars from a fixed series (``time + 4h <= now``); opens of started bars."""

    def __init__(self, candles_by_sym: dict[str, Sequence[Candle]]) -> None:
        self.bars = {s: list(cs) for s, cs in candles_by_sym.items()}
        self.times = {s: [c.time for c in cs] for s, cs in self.bars.items()}
        self.calls: list[tuple[str, int]] = []

    def closed_bars(self, symbol: str, start_s: int, now: datetime) -> list[Candle]:
        ts = self.times[symbol]
        lo = bisect.bisect_left(ts, start_s)
        hi = bisect.bisect_right(ts, int(now.timestamp()) - BAR_SECONDS)
        return self.bars[symbol][lo:hi]

    def bar_open(self, symbol: str, t_s: int, now: datetime) -> float | None:
        if now.timestamp() < t_s:
            return None
        i = bisect.bisect_left(self.times[symbol], t_s)
        if i < len(self.times[symbol]) and self.times[symbol][i] == t_s:
            return self.bars[symbol][i].open
        return None

    def last_price(self, symbol: str, now: datetime) -> float | None:
        self.calls.append(("last_price", int(now.timestamp())))
        i = bisect.bisect_right(self.times[symbol], int(now.timestamp())) - 1
        return self.bars[symbol][i].open if i >= 0 else None


def rs_portfolio(session, *, cash: float = 5000.0) -> PaperPortfolio:
    """A fresh RS-engine portfolio with a unique code (no cleanup needed between tests)."""
    code = f"RS_T_{uuid.uuid4().hex[:10]}"
    prof = deepcopy(RS_D1_PROFILE) | {"code": code}
    now = datetime.now(timezone.utc)
    pf = PaperPortfolio(code=code, label=code, currency="EUR", valuation_mode="USDT_AS_EUR_PROXY",
                        initial_cash=cash, cash=cash, realized_pnl=0.0, strategy_profile=prof, is_active=False,
                        started_at=now, created_at=now, updated_at=now)
    session.add(pf)
    session.commit()
    return pf


def no_klines(*_a, **_k):
    return []


def at(t_s: int) -> datetime:
    return datetime.fromtimestamp(t_s, tz=timezone.utc)
