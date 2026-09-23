"""Validation Engine (mission brief §15): runs a Synthetic Market Lab
scenario through the SAME decision pipeline app/screener/service.py uses for
live symbols, then compares what it actually decided against the scenario's
ground truth -- which the pipeline itself never receives.

`run_pipeline_over_candles` deliberately reuses the exact indicator/agent
functions scan_symbol calls (mission brief §11: "EXACTEMENT le même
pipeline"), just without the network fetch and without CVD/OI-Funding/MTF --
those three are enrichment-only in build_pipeline (they can never flip a
stage's PASS/FAIL by themselves), so omitting them cannot change the
decision being validated here.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from app.agents import ichimoku_agent, rvol_agent
from app.decision.pipeline import PipelineResult, build_pipeline
from app.indicators.ichimoku import Candle
from app.indicators.registry import REGISTRY
from app.synthetic.ground_truth import GroundTruth
from app.synthetic.scenarios import ALL_SCENARIOS, Scenario


def run_pipeline_over_candles(candles: list[Candle]) -> list[PipelineResult]:
    ichi_outputs = ichimoku_agent.analyze(candles)
    rvol_outputs = rvol_agent.analyze(candles)
    computed = REGISTRY.compute_many(
        ["structure", "atr", "location", "adx"],
        candles,
    )
    structure_states = computed["structure"]
    atr_states = computed["atr"]
    location_states = computed["location"]
    adx_states = computed["adx"]

    return [
        build_pipeline(
            ichimoku=ichi_outputs[i],
            rvol=rvol_outputs[i],
            structure=structure_states[i],
            atr=atr_states[i],
            location=location_states[i],
            adx=adx_states[i],
        )
        for i in range(len(candles))
    ]


@dataclass(frozen=True)
class ValidationResult:
    scenario: str
    ground_truth: GroundTruth
    all_decision_counts: dict[str, int]
    window_decision_counts: dict[str, int]
    dominant_window_decision: str | None
    passed: bool
    failure_reason: str | None


def validate_scenario(scenario: Scenario) -> ValidationResult:
    results = run_pipeline_over_candles(scenario.candles)
    start, end = scenario.ground_truth.eval_window
    window = results[start : end + 1]
    window_counts = Counter(r.decision for r in window)
    all_counts = Counter(r.decision for r in results)
    dominant = window_counts.most_common(1)[0][0] if window_counts else None

    if dominant is None:
        passed, failure_reason = False, "eval window produced no decisions"
    elif dominant in scenario.ground_truth.forbidden_decisions:
        passed = False
        failure_reason = f"dominant decision in eval window was forbidden: {dominant!r}"
    elif dominant not in scenario.ground_truth.acceptable_decisions:
        passed = False
        failure_reason = (
            f"dominant decision {dominant!r} not in acceptable set "
            f"{scenario.ground_truth.acceptable_decisions}"
        )
    else:
        passed, failure_reason = True, None

    return ValidationResult(
        scenario=scenario.ground_truth.scenario,
        ground_truth=scenario.ground_truth,
        all_decision_counts=dict(all_counts),
        window_decision_counts=dict(window_counts),
        dominant_window_decision=dominant,
        passed=passed,
        failure_reason=failure_reason,
    )


def run_lab() -> list[ValidationResult]:
    """Runs every catalogued scenario and returns one ValidationResult each
    -- the report described in mission brief §14 (scénario attendu / contexte
    détecté / signal / résultat / erreurs), in structured form.
    """
    return [validate_scenario(build()) for build in ALL_SCENARIOS]


def format_report(results: list[ValidationResult]) -> str:
    lines = ["Synthetic Market Lab -- validation report", ""]
    for r in results:
        status = "PASS" if r.passed else "FAIL"
        lines.append(f"[{status}] {r.scenario} (expected: {r.ground_truth.expected_context})")
        lines.append(f"  eval window decisions: {r.window_decision_counts}")
        lines.append(f"  full-series decisions:  {r.all_decision_counts}")
        if not r.passed:
            lines.append(f"  reason: {r.failure_reason}")
        lines.append("")
    n_passed = sum(1 for r in results if r.passed)
    lines.append(f"{n_passed}/{len(results)} scenarios passed")
    return "\n".join(lines)
