"""IchiVol analysis handoff package (deterministic stages, paper-only)."""

from app.analysis.adapters import (
    ENGINE_VERSION,
    analysis_stage_from_data_quality,
    compute_run_id,
    handoff_from_pipeline,
    pipeline_stage_to_analysis,
)
from app.analysis.stage import (
    AnalysisHandoff,
    AnalysisStage,
    AnalysisStageId,
    AnalysisStatus,
)

__all__ = [
    "ENGINE_VERSION",
    "AnalysisHandoff",
    "AnalysisStage",
    "AnalysisStageId",
    "AnalysisStatus",
    "analysis_stage_from_data_quality",
    "compute_run_id",
    "handoff_from_pipeline",
    "pipeline_stage_to_analysis",
]
