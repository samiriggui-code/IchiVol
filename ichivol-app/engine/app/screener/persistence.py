"""Persist a screener scan so every Decision is traceable back to the exact
candle/indicators/agent outputs that produced it (mission brief §9: "Pourquoi
le systeme a recommande BUY sur NVDA le 15 septembre a 10:00 ?").

`kind` on the stored StrategySignal reflects reality: it's the discrete
Ichimoku event (tk_long/tk_short/brk_long/brk_short) when one actually fired
on the scanned bar, and falls back to "state_scan" for a routine snapshot
where the agent is reporting a continuing bias rather than a fresh
cross/breakout -- the schema should never claim an event happened when it
didn't.
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.agents.types import StrategyAgentOutput
from app.db.models import AgentPrediction
from app.db.models import Candle as CandleRow
from app.db.models import Decision as DecisionRow
from app.db.models import StrategySignal
from app.market_data.collector import get_or_create_asset, upsert_candles
from app.screener.service import ScreenerRow

_BULLISH_BREAKOUT = "kumo_breakout_bullish"
_BEARISH_BREAKOUT = "kumo_breakout_bearish"
_BULLISH_CROSS = "bullish_tk_cross"
_BEARISH_CROSS = "bearish_tk_cross"


def _infer_signal_kind(ichimoku_output: StrategyAgentOutput) -> str:
    reasons = ichimoku_output.reasons
    if _BULLISH_BREAKOUT in reasons:
        return "brk_long"
    if _BEARISH_BREAKOUT in reasons:
        return "brk_short"
    if _BULLISH_CROSS in reasons:
        return "tk_long"
    if _BEARISH_CROSS in reasons:
        return "tk_short"
    return "state_scan"


def persist_scan(session: Session, row: ScreenerRow) -> DecisionRow:
    upsert_candles(
        session,
        symbol=row.symbol,
        exchange=row.exchange,
        timeframe=row.timeframe,
        candles=row.candles,
    )
    asset = get_or_create_asset(session, row.symbol, row.exchange)
    last_candle_time = datetime.fromtimestamp(row.candles[-1].time, tz=timezone.utc)
    candle_row = session.execute(
        select(CandleRow).where(
            CandleRow.asset_id == asset.id,
            CandleRow.timeframe == row.timeframe,
            CandleRow.timestamp == last_candle_time,
        )
    ).scalar_one()

    signal = StrategySignal(
        candle_id=candle_row.id,
        symbol=row.symbol,
        timeframe=row.timeframe,
        kind=_infer_signal_kind(row.ichimoku),
        rvol=row.rvol.metadata.get("rvol"),
    )
    session.add(signal)
    session.flush()

    for output in (row.ichimoku, row.rvol):
        session.add(
            AgentPrediction(
                signal_id=signal.id,
                agent=output.agent,
                direction=output.direction.value,
                probability=output.probability,
                confidence=output.confidence,
                expected_value=output.expected_value,
                reasons=output.reasons,
                invalidation=output.invalidation,
                metadata_=output.metadata,
            )
        )

    decision_row = DecisionRow(
        signal_id=signal.id,
        strategy_version=row.decision.strategy_version,
        decision=row.decision.decision,
        direction=row.decision.direction.value,
        probability=row.decision.probability,
        confidence=row.decision.confidence,
        agreement=row.decision.agreement,
        weights_used=row.decision.weights_used,
        reasons=row.decision.reasons,
        risks=row.decision.risks,
        invalidation=row.decision.invalidation,
    )
    session.add(decision_row)
    session.commit()
    session.refresh(decision_row)
    return decision_row
