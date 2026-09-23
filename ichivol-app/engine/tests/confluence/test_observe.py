"""T5a — observe_family_weights is deterministic and never mutates pipeline."""

from __future__ import annotations

from app.agents.types import Direction, StrategyAgentOutput
from app.confluence.observe import observe_family_weights
from app.confluence.weights import FamilyWeightsConfig
from app.decision.pipeline import StageStatus, build_pipeline
from app.indicators.atr import AtrState, VolatilityRegime
from app.indicators.structure import BosEvent, StructureBias, StructureState


def _ichi(direction: Direction = Direction.LONG, confidence: float = 1.0) -> StrategyAgentOutput:
    return StrategyAgentOutput(
        agent="ICHIMOKU_AGENT",
        direction=direction,
        probability=0.7,
        confidence=confidence,
        expected_value=0.0,
        reasons=["tk_cross_bullish"],
        invalidation=[],
        metadata={"score": 50.0},
    )


def _rvol(confirmed: bool = True) -> StrategyAgentOutput:
    return StrategyAgentOutput(
        agent="RVOL_AGENT",
        direction=Direction.NEUTRAL,
        probability=0.5,
        confidence=0.8 if confirmed else 0.2,
        expected_value=0.0,
        reasons=["rvol_confirmed"] if confirmed else ["rvol_low"],
        invalidation=[],
        metadata={
            "confirmed": confirmed,
            "anomaly_level": "SIGNIFICANT" if confirmed else "LOW",
            "rvol": 2.5 if confirmed else 0.4,
        },
    )


def _structure_bull() -> StructureState:
    return StructureState(
        time=0,
        last_swing_high=110.0,
        last_swing_low=90.0,
        bias=StructureBias.BULLISH,
        bos=BosEvent.BULLISH,
    )


def _atr_normal() -> AtrState:
    return AtrState(
        time=0,
        true_range=1.0,
        atr=1.5,
        percentile=0.5,
        regime=VolatilityRegime.NORMAL,
        suggested_stop_distance=3.0,
    )


def test_observation_deterministic_and_complete():
    pipe = build_pipeline(
        _ichi(),
        _rvol(True),
        structure=_structure_bull(),
        atr=_atr_normal(),
    )
    a = observe_family_weights(pipe)
    b = observe_family_weights(pipe)
    assert a.to_dict() == b.to_dict()
    assert set(a.family_status) == {
        "direction",
        "participation",
        "structure",
        "location",
        "regime",
    }
    assert a.pipeline_decision == pipe.decision
    assert "does not alter" in a.disclaimer.lower()


def test_weighted_support_all_pass():
    pipe = build_pipeline(
        _ichi(),
        _rvol(True),
        structure=_structure_bull(),
        atr=_atr_normal(),
    )
    # location may be pending without LocationState — force equal weights all-pass via custom config
    # Use actual statuses from pipeline for contribution math check.
    obs = observe_family_weights(pipe)
    expected = 0.0
    for fam, status in obs.family_status.items():
        score = {"pass": 1.0, "watch": 0.0, "fail": -1.0, "pending": 0.0, "skip": 0.0}[status]
        expected += obs.weights[fam] * score
    assert abs(obs.weighted_support - expected) < 1e-9


def test_fail_stage_reduces_support():
    good = build_pipeline(
        _ichi(),
        _rvol(True),
        structure=_structure_bull(),
        atr=_atr_normal(),
    )
    bad = build_pipeline(
        _ichi(),
        _rvol(False),  # participation FAIL
        structure=_structure_bull(),
        atr=_atr_normal(),
    )
    assert observe_family_weights(good).weighted_support > observe_family_weights(bad).weighted_support
    assert observe_family_weights(bad).family_status["participation"] == StageStatus.FAIL.value


def test_observe_does_not_mutate_pipeline():
    pipe = build_pipeline(
        _ichi(),
        _rvol(True),
        structure=_structure_bull(),
        atr=_atr_normal(),
    )
    before_decision = pipe.decision
    before_direction = pipe.direction
    before_stages = [(s.id, s.status, s.summary, list(s.codes)) for s in pipe.stages]
    observe_family_weights(pipe)
    assert pipe.decision == before_decision
    assert pipe.direction == before_direction
    after_stages = [(s.id, s.status, s.summary, list(s.codes)) for s in pipe.stages]
    assert after_stages == before_stages


def test_custom_config_equal_weights():
    from app.confluence.families import ALL_FAMILIES

    cfg = FamilyWeightsConfig(weights={f.value: 0.2 for f in ALL_FAMILIES})
    pipe = build_pipeline(_ichi(), _rvol(True))
    obs = observe_family_weights(pipe, cfg)
    assert obs.weights["direction"] == 0.2
    assert abs(sum(obs.weights.values()) - 1.0) < 1e-12
