"""End-to-end check that the migrated schema actually round-trips a full
Candle -> IchimokuIndicator -> StrategySignal -> AgentPrediction -> Decision
chain against the real `ichivol_engine_dev` Postgres database.

Skipped automatically if that database isn't reachable (e.g. CI without
Postgres) rather than failing the whole suite -- the pure-Python indicator
and agent tests (tests/indicators, tests/agents) don't need a DB at all and
must keep passing regardless.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy.exc import OperationalError

from app.db.models import AgentPrediction, Asset, Candle, Decision, IchimokuIndicator, StrategySignal
from app.db.session import SessionLocal, engine

try:
    with engine.connect():
        pass
    DB_AVAILABLE = True
except OperationalError:
    DB_AVAILABLE = False

pytestmark = pytest.mark.skipif(not DB_AVAILABLE, reason="ichivol_engine_dev Postgres not reachable")


def test_full_chain_round_trips():
    session = SessionLocal()
    try:
        asset = Asset(symbol="TESTUSDT", exchange="binance")
        session.add(asset)
        session.flush()

        candle = Candle(
            asset_id=asset.id,
            timeframe="1h",
            timestamp=datetime.now(timezone.utc),
            open=100.0,
            high=101.0,
            low=99.0,
            close=100.5,
            volume=1234.0,
        )
        session.add(candle)
        session.flush()

        ichi = IchimokuIndicator(
            candle_id=candle.id,
            tenkan=100.2,
            kijun=99.8,
            price_vs_kumo="ABOVE",
            tk_cross="BULLISH",
            score=62.5,
        )
        session.add(ichi)

        signal = StrategySignal(
            candle_id=candle.id,
            symbol="TESTUSDT",
            timeframe="1h",
            kind="tk_long",
            rvol=2.4,
        )
        session.add(signal)
        session.flush()

        prediction = AgentPrediction(
            signal_id=signal.id,
            agent="ICHIMOKU_AGENT",
            direction="LONG",
            probability=0.81,
            confidence=1.0,
            expected_value=0.0,
            reasons=["price_above_kumo", "bullish_tk_cross"],
            invalidation=["bearish_tk_cross"],
            metadata_={"score": 62.5},
        )
        session.add(prediction)

        decision = Decision(
            signal_id=signal.id,
            decision="BUY",
            direction="LONG",
            probability=0.81,
            confidence=1.0,
            agreement=1.0,
            weights_used={"ICHIMOKU_AGENT": 0.6, "RVOL_AGENT": 0.4},
            reasons=["price_above_kumo", "high_relative_volume"],
            risks=["thin_liquidity"],
            invalidation=["bearish_tk_cross"],
        )
        session.add(decision)
        session.flush()

        decision_id = decision.id
        session.commit()

        reloaded = session.get(Decision, decision_id)
        assert reloaded is not None
        assert reloaded.decision == "BUY"
        assert reloaded.signal.symbol == "TESTUSDT"
        assert reloaded.signal.candle.ichimoku.price_vs_kumo == "ABOVE"
        assert reloaded.signal.predictions[0].metadata_ == {"score": 62.5}
    finally:
        session.rollback()
        session.query(Decision).delete()
        session.query(AgentPrediction).delete()
        session.query(StrategySignal).delete()
        session.query(IchimokuIndicator).delete()
        session.query(Candle).delete()
        session.query(Asset).delete()
        session.commit()
        session.close()
