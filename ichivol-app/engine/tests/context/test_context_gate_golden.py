"""Golden parity — context gate via REGISTRY."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.agents.types import Direction
from app.context.gate import apply_context_gate
from app.decision.pipeline import PipelineResult, PipelineStage, StageId, StageStatus
from app.paper.strategy_profiles import ICHIVOL_CTX_FULL
from tests.indicators.test_ichimoku_lookahead import _make_candles

_FIXTURE = Path(__file__).resolve().parent / "fixtures" / "context_gate_golden.json"


@pytest.mark.parametrize("seed", [7, 42])
def test_context_gate_matches_golden(seed: int):
    golden = json.loads(_FIXTURE.read_text(encoding="utf-8"))[f"seed_{seed}"]
    pipe = PipelineResult(
        decision="BUY",
        direction=Direction.LONG,
        stages=[PipelineStage(StageId.REGIME, StageStatus.PASS, "ok", [])],
    )
    gate = apply_context_gate(pipe, _make_candles(300, seed=seed), ICHIVOL_CTX_FULL)
    actual = {
        "blocked": gate.blocked,
        "reason": gate.reason,
        "raw_decision": gate.raw_decision,
        "pipeline_decision": gate.pipeline.decision,
        "context_payload": gate.context_payload,
        "pipeline_stages": [
            {
                "id": s.id.value if hasattr(s.id, "value") else str(s.id),
                "status": s.status.value if hasattr(s.status, "value") else str(s.status),
                "summary": s.summary,
                "codes": list(s.codes),
            }
            for s in gate.pipeline.stages
        ],
    }
    assert actual == golden
