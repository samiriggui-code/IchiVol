"""Adapters from existing pipeline / agents into AnalysisStage handoffs."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from app.analysis.stage import (
    AnalysisHandoff,
    AnalysisStage,
    AnalysisStageId,
    AnalysisStatus,
)
from app.decision.pipeline import PipelineResult, PipelineStage, StageId, StageStatus

ENGINE_VERSION = "ichivol_analysis_v0"

_PIPELINE_STATUS: dict[StageStatus, AnalysisStatus] = {
    StageStatus.PASS: AnalysisStatus.PASS,
    StageStatus.FAIL: AnalysisStatus.FAIL,
    StageStatus.WATCH: AnalysisStatus.WATCH,
    StageStatus.PENDING: AnalysisStatus.PENDING,
    StageStatus.SKIP: AnalysisStatus.SKIP,
}

_PIPELINE_STAGE_ID: dict[StageId, AnalysisStageId] = {
    StageId.DIRECTION: AnalysisStageId.ICHIMOKU,
    StageId.PARTICIPATION: AnalysisStageId.VOLUME,
    StageId.STRUCTURE: AnalysisStageId.STRUCTURE,
    StageId.LOCATION: AnalysisStageId.LOCATION,
    StageId.REGIME: AnalysisStageId.REGIME,
}


def map_pipeline_status(status: StageStatus) -> AnalysisStatus:
    mapped = _PIPELINE_STATUS.get(status)
    if mapped is None:
        raise ValueError(f"unknown StageStatus: {status!r}")
    return mapped


def map_pipeline_stage_id(stage_id: StageId) -> AnalysisStageId:
    mapped = _PIPELINE_STAGE_ID.get(stage_id)
    if mapped is None:
        raise ValueError(f"unknown StageId: {stage_id!r}")
    return mapped


def pipeline_stage_to_analysis(
    stage: PipelineStage,
    *,
    symbol: str = "",
    timeframe: str = "",
    stage_version: str = "ichivol_pipeline_v1",
) -> AnalysisStage:
    """Convert one live pipeline stage without changing its semantics.

    FAIL on REGIME stays FAIL (not auto-VETO) so behavior matches today's
    gates. Explicit VETO is reserved for the dedicated Risk coordinator.
    """
    return AnalysisStage(
        stage_id=map_pipeline_stage_id(stage.id),
        stage_version=stage_version,
        status=map_pipeline_status(stage.status),
        reason=stage.summary,
        symbol=symbol,
        timeframe=timeframe,
        evidence=list(stage.codes),
        metrics={"pipeline_stage_id": stage.id.value},
    )


def handoff_from_pipeline(
    pipeline: PipelineResult,
    *,
    symbol: str,
    timeframe: str,
    market_data_hash: str | None = None,
    config: dict[str, Any] | None = None,
    engine_version: str = ENGINE_VERSION,
) -> AnalysisHandoff:
    """Build a deterministic handoff from an existing PipelineResult."""
    cfg = dict(config or {})
    stages = tuple(
        pipeline_stage_to_analysis(
            s,
            symbol=symbol,
            timeframe=timeframe,
            stage_version=pipeline.strategy_version,
        )
        for s in pipeline.stages
    )
    run_id = compute_run_id(
        engine_version=engine_version,
        symbol=symbol,
        timeframe=timeframe,
        decision=pipeline.decision,
        stages=stages,
        market_data_hash=market_data_hash,
        config=cfg,
    )
    return AnalysisHandoff(
        run_id=run_id,
        engine_version=engine_version,
        symbol=symbol,
        timeframe=timeframe,
        stages=stages,
        market_data_hash=market_data_hash,
        decision=pipeline.decision,
        config=cfg,
    )


def compute_run_id(
    *,
    engine_version: str,
    symbol: str,
    timeframe: str,
    decision: str | None,
    stages: tuple[AnalysisStage, ...] | list[AnalysisStage],
    market_data_hash: str | None,
    config: dict[str, Any],
) -> str:
    """Stable short id — same inputs ⇒ same run_id (GPTHEIST-style)."""
    payload = {
        "engine_version": engine_version,
        "symbol": symbol,
        "timeframe": timeframe,
        "decision": decision,
        "market_data_hash": market_data_hash,
        "config": config,
        "stages": [s.to_dict() for s in stages],
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
