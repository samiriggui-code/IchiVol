"""Runs every catalogued Synthetic Market Lab scenario through the real
pipeline and checks it against ground truth. If one of these fails, it means
either the generator's scenario isn't shaped the way its docstring claims,
or the pipeline is misinterpreting a configuration whose correct read is
known in advance -- worth investigating either way, never silencing.
"""

from __future__ import annotations

from app.synthetic import scenarios
from app.synthetic.validation import format_report, run_lab, validate_scenario


def test_bullish_trend_scenario_matches_ground_truth():
    result = validate_scenario(scenarios.bullish_trend())
    assert result.passed, result.failure_reason


def test_bearish_trend_scenario_matches_ground_truth():
    result = validate_scenario(scenarios.bearish_trend())
    assert result.passed, result.failure_reason


def test_false_breakout_scenario_matches_ground_truth():
    result = validate_scenario(scenarios.false_breakout())
    assert result.passed, result.failure_reason


def test_low_volume_bullish_scenario_matches_ground_truth():
    result = validate_scenario(scenarios.low_volume_bullish())
    assert result.passed, result.failure_reason


def test_range_scenario_matches_ground_truth():
    result = validate_scenario(scenarios.range_market())
    assert result.passed, result.failure_reason


def test_run_lab_covers_every_catalogued_scenario():
    results = run_lab()
    assert len(results) == len(scenarios.ALL_SCENARIOS)
    assert {r.scenario for r in results} == {
        scenarios.SCENARIO_A_BULLISH_TREND,
        scenarios.SCENARIO_B_BEARISH_TREND,
        scenarios.SCENARIO_D_FALSE_BREAKOUT,
        scenarios.SCENARIO_E_LOW_VOLUME_BULLISH,
        scenarios.SCENARIO_G_RANGE,
    }


def test_format_report_is_human_readable():
    report = format_report(run_lab())
    assert "Synthetic Market Lab" in report
    assert "scenarios passed" in report
