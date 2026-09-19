"""Tests for AnalysisStage contract + pipeline adapter (Phase 2)."""

from __future__ import annotations

import json

from app.agents.types import Direction, StrategyAgentOutput
from app.analysis import AnalysisStatus, handoff_from_pipeline
from app.analysis.adapters import map_pipeline_stage_id, map_pipeline_status
from app.analysis.stage import AnalysisHandoff, AnalysisStage, AnalysisStageId
from app.decision.pipeline import StageId, StageStatus, build_pipeline
from app.indicators.atr import AtrState, VolatilityRegime
from app.indicators.structure import BosEvent, StructureBias, StructureState


def _agent(agent: str, direction: Direction, confidence: float, **metadata) -> StrategyAgentOutput:
    return StrategyAgentOutput(
        agent=agent,
        direction=direction,
        probability=0.7,
        confidence=confidence,
        expected_value=0.0,
        reasons=[],
        invalidation=[],
        metadata=metadata,
    )


def _ichi(direction: Direction = Direction.LONG) -> StrategyAgentOutput:
    return _agent("ICHIMOKU_AGENT", direction, 1.0, score=50.0)


def _rvol(confirmed: bool = True) -> StrategyAgentOutput:
    return _agent(
        "RVOL_AGENT",
        Direction.NEUTRAL,
        0.5,
        confirmed=confirmed,
        anomaly_level="SIGNIFICANT" if confirmed else "LOW",
        rvol=2.0 if confirmed else 0.5,
    )


def _structure(bias: StructureBias = StructureBias.BULLISH) -> StructureState:
    return StructureState(
        time=0,
        last_swing_high=110.0,
        last_swing_low=90.0,
        bias=bias,
        bos=BosEvent.BULLISH if bias == StructureBias.BULLISH else BosEvent.NONE,
    )


def _atr(regime: VolatilityRegime = VolatilityRegime.NORMAL) -> AtrState:
    return AtrState(
        time=0,
        true_range=1.0,
        atr=1.0,
        percentile=0.5,
        regime=regime,
        suggested_stop_distance=1.5,
    )


def test_analysis_stage_json_roundtrip():
    stage = AnalysisStage(
        stage_id=AnalysisStageId.VOLUME,
        stage_version="v1",
        status=AnalysisStatus.PASS,
        reason="RVOL 1.80×",
        symbol="BTCUSDT",
        timeframe="1h",
        confidence=0.7,
        metrics={"rvol": 1.8},
        evidence=["rvol_confirmed"],
        warnings=[],
    )
    restored = AnalysisStage.from_dict(stage.to_dict())
    assert restored == stage
    json.dumps(stage.to_dict())


def test_handoff_from_pipeline_deterministic():
    pipeline = build_pipeline(
        ichimoku=_ichi(),
        rvol=_rvol(),
        structure=_structure(),
        atr=_atr(),
        mtf_aligned=True,
    )
    a = handoff_from_pipeline(pipeline, symbol="BTCUSDT", timeframe="1h", market_data_hash="abc")
    b = handoff_from_pipeline(pipeline, symbol="BTCUSDT", timeframe="1h", market_data_hash="abc")
    assert a.to_dict() == b.to_dict()
    assert a.run_id == b.run_id
    assert a.decision == pipeline.decision
    assert len(a.stages) == len(pipeline.stages)
    assert a.stages[0].stage_id == AnalysisStageId.ICHIMOKU
    assert a.has_veto() is False


def test_status_mapping_exhaustive_pipeline_values():
    for status in StageStatus:
        mapped = map_pipeline_status(status)
        assert isinstance(mapped, AnalysisStatus)


def test_stage_id_mapping_exhaustive():
    for sid in StageId:
        mapped = map_pipeline_stage_id(sid)
        assert isinstance(mapped, AnalysisStageId)


def test_veto_detection():
    handoff = handoff_from_pipeline(
        build_pipeline(ichimoku=_ichi(), rvol=_rvol(), structure=_structure(), atr=_atr()),
        symbol="ETHUSDT",
        timeframe="1h",
    )
    veto = AnalysisStage(
        stage_id=AnalysisStageId.RISK,
        stage_version="v1",
        status=AnalysisStatus.VETO,
        reason="extreme_volatility",
        evidence=["atr_extreme"],
    )
    with_veto = AnalysisHandoff(
        run_id="x",
        engine_version=handoff.engine_version,
        symbol="ETHUSDT",
        timeframe="1h",
        stages=handoff.stages + (veto,),
        decision="NO_TRADE",
    )
    assert with_veto.has_veto()
    assert "extreme_volatility" in with_veto.veto_reasons()
