"""Tests for paper order intent (propose before act)."""

from __future__ import annotations

from app.agents import ichimoku_agent, rvol_agent
from app.db.session import SessionLocal
from app.decision.pipeline import build_pipeline
from app.indicators.atr import compute_atr
from app.indicators.ichimoku import Candle
from app.market_data.volume_semantics import VolumeType
from app.paper.intent import propose_order_intent
from app.paper.portfolio import ensure_baseline_portfolio
from app.screener.service import ScreenerRow
from app.decision.combiner import combine_ichimoku_rvol


def _candles(n: int = 120) -> list[Candle]:
    out = []
    for i in range(n):
        px = 100 + i * 0.5
        v = 300.0 if i == n - 1 else 100.0
        out.append(
            Candle(
                time=1_700_000_000 + i * 3600,
                open=px,
                high=px + 1,
                low=px - 1,
                close=px + 0.4,
                volume=v,
                volume_type=VolumeType.EXCHANGE_VOLUME,
            )
        )
    return out


def test_propose_intent_blocked_when_watch():
    candles = _candles()
    ichi = ichimoku_agent.analyze(candles)[-1]
    rvol = rvol_agent.analyze(candles)[-1]
    # Force low participation → WATCH-ish pipeline often; build row anyway
    decision = combine_ichimoku_rvol(ichi, rvol)
    pipeline = build_pipeline(ichimoku=ichi, rvol=rvol, atr=compute_atr(candles)[-1])
    row = ScreenerRow(
        symbol="BTCUSDT",
        exchange="binance",
        timeframe="1h",
        price=candles[-1].close,
        candles=candles,
        ichimoku=ichi,
        rvol=rvol,
        decision=decision,
        pipeline=pipeline,
        atr=compute_atr(candles)[-1],
    )
    session = SessionLocal()
    try:
        ensure_baseline_portfolio(session)
        session.commit()
        intent = propose_order_intent(session, row)
        assert intent.symbol == "BTCUSDT"
        assert intent.to_dict()["reason"] in (
            "ok",
            "not_actionable",
            "no_stop",
            "insufficient_cash_or_risk",
        )
        if intent.actionable:
            assert intent.qty and intent.qty > 0
            assert intent.stop_price is not None
            assert intent.take_profit_price is not None
    finally:
        session.close()
