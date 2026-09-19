"""IchiVol analysis handoff package (deterministic stages, paper-only)."""

from app.analysis.adapters import (
    ENGINE_VERSION,
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
    "compute_run_id",
    "handoff_from_pipeline",
    "pipeline_stage_to_analysis",
]
