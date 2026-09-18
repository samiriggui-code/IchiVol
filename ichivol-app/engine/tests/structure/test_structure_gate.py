"""Tests for optional Market Structure paper gate."""

from __future__ import annotations

import random

from app.agents.types import Direction
from app.decision.pipeline import PipelineResult, PipelineStage, StageId, StageStatus
from app.indicators.ichimoku import Candle
from app.paper.strategy_profiles import BASELINE_PROFILE, STRUCTURE_CONSENSUS, profile_for
from app.structure.gate import apply_structure_gate


def _candles(n: int = 120, seed: int = 1) -> list[Candle]:
    rng = random.Random(seed)
    price = 100.0
    out: list[Candle] = []
    for i in range(n):
        o = price
        c = max(1.0, price + rng.uniform(-1, 1.2))
        h = max(o, c) + rng.uniform(0.2, 1.0)
        l = min(o, c) - rng.uniform(0.2, 1.0)
        out.append(Candle(time=i, open=o, high=h, low=l, close=c, volume=100))
        price = c
    return out


def _buy_pipeline() -> PipelineResult:
    return PipelineResult(
        decision="BUY",
        direction=Direction.LONG,
        stages=[
            PipelineStage(StageId.DIRECTION, StageStatus.PASS, "LONG", []),
            PipelineStage(StageId.PARTICIPATION, StageStatus.PASS, "RVOL ok", []),
            PipelineStage(StageId.STRUCTURE, StageStatus.PASS, "aligned", []),
            PipelineStage(StageId.LOCATION, StageStatus.PASS, "ok", []),
            PipelineStage(StageId.REGIME, StageStatus.PASS, "normal", []),
        ],
    )


def test_baseline_profile_never_blocks():
    gate = apply_structure_gate(_buy_pipeline(), _candles(), BASELINE_PROFILE)
    assert gate.blocked is False
    assert gate.pipeline.decision == "BUY"


def test_structure_profile_has_filter_config():
    profile = profile_for("STRUCTURE_CONSENSUS")
    assert profile["structure_filter"] == "block_near_opposing"
    assert "mvpp" in profile["structure_detectors"]
    assert profile["shadow_on_block"] is True


def test_structure_gate_runs_without_crash():
    gate = apply_structure_gate(_buy_pipeline(), _candles(150), STRUCTURE_CONSENSUS, rvol=1.5)
    assert gate.raw_decision == "BUY"
    assert gate.pipeline.decision in ("BUY", "NO_TRADE")
    if gate.blocked:
        assert gate.pipeline.decision == "NO_TRADE"
        assert gate.structure_payload is not None
