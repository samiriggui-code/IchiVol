"""T5b — family weight profiles + compare + study."""

from __future__ import annotations

from app.agents.types import Direction, StrategyAgentOutput
from app.confluence.compare import compare_family_weight_profiles
from app.confluence.profiles import (
    FAMILY_WEIGHT_PROFILES,
    get_family_weight_profile,
    list_family_weight_profiles,
)
from app.confluence.study import run_family_weights_study
from app.decision.pipeline import build_pipeline
from app.indicators.atr import AtrState, VolatilityRegime
from app.indicators.structure import BosEvent, StructureBias, StructureState
from app.synthetic.generator import GeneratorParams, Regime, generate_market


def _ichi() -> StrategyAgentOutput:
    return StrategyAgentOutput(
        agent="ICHIMOKU_AGENT",
        direction=Direction.LONG,
        probability=0.7,
        confidence=1.0,
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
        reasons=[],
        invalidation=[],
        metadata={
            "confirmed": confirmed,
            "anomaly_level": "SIGNIFICANT" if confirmed else "LOW",
            "rvol": 2.5 if confirmed else 0.4,
        },
    )


def test_profiles_catalog_valid():
    profiles = list_family_weight_profiles()
    assert len(profiles) >= 4
    assert "balanced_v0" in FAMILY_WEIGHT_PROFILES
    for p in profiles:
        p.config.validate()
        assert abs(sum(p.config.weights.values()) - 1.0) < 1e-9


def test_get_profile():
    p = get_family_weight_profile("direction_heavy_v0")
    assert p.config.weights["direction"] == 0.45


def test_compare_profiles_deterministic():
    pipe = build_pipeline(
        _ichi(),
        _rvol(True),
        structure=StructureState(
            time=0,
            last_swing_high=110.0,
            last_swing_low=90.0,
            bias=StructureBias.BULLISH,
            bos=BosEvent.BULLISH,
        ),
        atr=AtrState(
            time=0,
            true_range=1.0,
            atr=1.5,
            percentile=0.5,
            regime=VolatilityRegime.NORMAL,
            suggested_stop_distance=3.0,
        ),
    )
    a = compare_family_weight_profiles(pipe)
    b = compare_family_weight_profiles(pipe)
    assert a == b
    assert "balanced_v0" in a["profiles"]
    assert a["pipeline_decision"] == pipe.decision
    assert "does not alter" in a["disclaimer"].lower()
    # Different profiles can disagree on support when statuses mix pass/fail
    supports = {pid: row["weighted_support"] for pid, row in a["profiles"].items()}
    assert "direction_heavy_v0" in supports


def test_compare_does_not_mutate_pipeline():
    pipe = build_pipeline(_ichi(), _rvol(True))
    before = pipe.decision
    compare_family_weight_profiles(pipe)
    assert pipe.decision == before


def test_study_on_synthetic_no_crash():
    candles = generate_market(
        Regime.BULLISH_TREND, GeneratorParams(n=200, seed=42)
    )
    assert len(candles) >= 100
    report = run_family_weights_study(
        candles,
        symbol="SYN",
        timeframe="1h",
        step=5,
        sample_limit=5,
        min_bars=60,
    )
    d = report.to_dict()
    assert d["n_bars"] == len(candles)
    assert set(d["profile_ids"]) == set(FAMILY_WEIGHT_PROFILES)
    assert "does not alter" in d["disclaimer"].lower()
    for agg in d["aggregates"]:
        assert agg["n_signals"] == d["n_signals"]
