"""Evidence DB persistence tests."""

from __future__ import annotations

from app.agents import ichimoku_agent, rvol_agent
from app.decision.pipeline import build_pipeline
from app.db.models import SignalEvidenceRecord
from app.db.session import SessionLocal
from app.evidence.context import build_signal_context
from app.evidence.engine import EvidenceEngine
from app.evidence.persistence import attach_outcome, persist_evidence
from app.indicators.ichimoku import Candle
from app.market_data.volume_semantics import VolumeType


def _candles(n: int = 100) -> list[Candle]:
    return [
        Candle(
            time=1_700_000_000 + i * 3600,
            open=100 + i,
            high=101 + i,
            low=99 + i,
            close=100.5 + i,
            volume=50.0 if i < n - 1 else 200.0,
            volume_type=VolumeType.EXCHANGE_VOLUME,
        )
        for i in range(n)
    ]


def test_persist_and_attach_outcome():
    candles = _candles()
    ichi = ichimoku_agent.analyze(candles)[-1]
    rvol = rvol_agent.analyze(candles)[-1]
    pipeline = build_pipeline(ichimoku=ichi, rvol=rvol)
    ctx = build_signal_context(
        symbol="BTCUSDT",
        timeframe="1h",
        candles=candles,
        provider="binance",
        asset_class="crypto",
        ichimoku=ichi,
        rvol=rvol,
        pipeline=pipeline,
    )
    report = EvidenceEngine().evaluate(ctx, [])
    session = SessionLocal()
    try:
        row = persist_evidence(session, report=report, decision=pipeline.decision)
        session.commit()
        eid = row.id
        assert session.get(SignalEvidenceRecord, eid) is not None
        updated = attach_outcome(
            session,
            eid,
            forward_returns={"10": 0.012},
            mfe_pct=0.03,
            mae_pct=0.01,
            target_hit=True,
            invalidation_hit=False,
        )
        session.commit()
        assert updated is not None
        assert updated.outcome_json is not None
        assert updated.outcome_json["mfe_pct"] == 0.03
        assert updated.volume_type == VolumeType.EXCHANGE_VOLUME.value
    finally:
        # cleanup
        row = session.get(SignalEvidenceRecord, eid)
        if row is not None:
            session.delete(row)
            session.commit()
        session.close()
