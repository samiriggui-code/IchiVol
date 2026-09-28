"""RS-09 §8.1 — replaying 2024 through the live path gives the trades of rs.simulate.

Live path = RsD1Runner (one cycle per 4h close, fills at the open of the bar in progress, stops via the
protection monitor with no 1m data -> book fallback on the 4h bar, Postgres writes). Needs the local VP1
4h series (not in git): skipped when absent.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy import select

from app.db.models import PaperPosition
from app.db.session import SessionLocal
from app.paper.rs_d1_runner import RsD1Runner
from rs import BAR_SECONDS, DATA_END_EXCL, SYMBOLS
from rs.costs import cost_profile
from rs.data import load_symbol
from rs.donchian import simulate
from tests.rs_paper.helpers import FakeSource, at, no_klines, rs_portfolio

VP1_4H = Path(__file__).resolve().parents[2] / "vp1" / "data" / "series" / "BTCUSDT_spot_4h_20200901_20260831.json"
SCORE_2024 = int(datetime(2024, 1, 1, tzinfo=timezone.utc).timestamp())
HISTORY_START = SCORE_2024 - 200 * BAR_SECONDS


@pytest.mark.skipif(not VP1_4H.exists(), reason="VP1 4h series not available locally")
def test_replay_2024_live_path_equals_simulate():
    candles = {}
    for s in SYMBOLS:
        cs, _ = load_symbol(s)  # truncated < 2025 (assertion inside)
        candles[s] = [c for c in cs if c.time >= HISTORY_START]
    sim = simulate(candles, cost_profile("paper"), score_start=SCORE_2024, data_end_excl=DATA_END_EXCL)
    sim_closed = [t for t in sim.trades if t.exit_time is not None]
    assert len(sim_closed) >= 10  # the year has real activity

    session = SessionLocal()
    try:
        pf = rs_portfolio(session)
        runner = RsD1Runner(FakeSource(candles), code=pf.code, symbols=SYMBOLS, klines_1m_fn=no_klines,
                            trades_fn=None, history_start=HISTORY_START, replay_score_start=SCORE_2024)
        times = sorted({c.time for cs in candles.values() for c in cs})
        for t in times:
            runner.cycle(session, now=at(t + BAR_SECONDS + 1))
        book = runner._cache[2]

        # 1) the book driven by the live path is the backtest, trade for trade (exact)
        assert book.trades == sim_closed
        assert book.rej == sim.rejections
        assert book.halt_days == sim.halt_days

        # 2) the paper tables hold the same trades (fills recorded by the broker, float tolerance)
        session.expire_all()
        rows = session.execute(
            select(PaperPosition).where(PaperPosition.portfolio_id == pf.id).order_by(PaperPosition.entry_time, PaperPosition.symbol)
        ).scalars().all()
        closed = [r for r in rows if r.status == "CLOSED"]
        assert len(closed) == len(sim_closed)
        by_key = {(t.symbol, t.entry_time): t for t in sim_closed}
        for r in closed:
            tr = by_key[(r.symbol, int(r.entry_time.timestamp()) - 1)]
            assert r.entry_price == tr.entry_fill
            assert r.qty == pytest.approx(tr.qty, rel=0, abs=0)
            assert r.exit_price == pytest.approx(tr.exit_fill, rel=1e-12)
            assert r.realized_pnl == pytest.approx(tr.net, rel=1e-9, abs=1e-9)
            assert r.exit_reason == f"rs_{tr.exit_reason}"
        session.refresh(pf)
        assert pf.cash == pytest.approx(book.cash, rel=1e-12)
    finally:
        session.close()
