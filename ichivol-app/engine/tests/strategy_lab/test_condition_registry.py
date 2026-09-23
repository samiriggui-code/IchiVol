"""T3c — ConditionSpec registry contracts and ratchet."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from app.agents.types import Direction
from app.indicators.registry import REGISTRY
from app.strategy_lab.conditions import CONDITION_REGISTRY, ConditionSpec
from app.strategy_lab.features import FeatureBar, build_feature_series
from app.strategy_lab.ruleset import CONDITION_ENUMS, CONDITION_SCHEMA, parse_ruleset
from tests.indicators.test_ichimoku_lookahead import _make_candles

_EVALUATOR = (
    Path(__file__).resolve().parents[2]
    / "app"
    / "strategy_lab"
    / "evaluator.py"
)
_COMPOSITE_IDS = frozenset({"structure", "derived"})


def test_condition_schema_derived_from_registry():
    assert CONDITION_SCHEMA == {
        k: spec.value_type for k, spec in CONDITION_REGISTRY.items()
    }


def test_condition_enums_derived_from_allowed_values():
    expected = {
        k: frozenset(spec.allowed_values)
        for k, spec in CONDITION_REGISTRY.items()
        if spec.allowed_values is not None
    }
    assert CONDITION_ENUMS == expected


def test_no_duplicate_condition_keys():
    assert len(CONDITION_REGISTRY) == len(set(CONDITION_REGISTRY))


def test_indicator_ids_exist_or_composite():
    for key, spec in CONDITION_REGISTRY.items():
        if spec.indicator_id in _COMPOSITE_IDS:
            continue
        assert spec.indicator_id in REGISTRY, (
            f"{key}: indicator_id {spec.indicator_id!r} not in REGISTRY"
        )


def test_evaluator_has_no_key_equality_chain():
    """Cliquet: evaluator must not compare key == \"…\" anymore."""
    source = _EVALUATOR.read_text(encoding="utf-8")
    tree = ast.parse(source)
    offenders: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Compare):
            continue
        left = node.left
        if not (isinstance(left, ast.Name) and left.id == "key"):
            continue
        for op, comparator in zip(node.ops, node.comparators):
            if isinstance(op, ast.Eq) and isinstance(comparator, ast.Constant):
                if isinstance(comparator.value, str):
                    offenders.append(comparator.value)
    assert not offenders, f"evaluator still has key == ... for {offenders}"


def test_adding_condition_is_one_declaration():
    """Local ConditionSpec becomes parsable + evaluable without editing ruleset/evaluator."""
    import app.strategy_lab.evaluator as eval_mod
    from app.strategy_lab import ruleset as ruleset_mod
    from app.strategy_lab.evaluator import _condition_holds

    key = "_t3c_test_always_true"
    assert key not in CONDITION_REGISTRY

    def holds(bar: FeatureBar, expected, direction: Direction) -> bool:
        return bool(expected)

    local = dict(CONDITION_REGISTRY)
    local[key] = ConditionSpec(
        key=key,
        value_type=bool,
        indicator_id="derived",
        holds=holds,
        description="test-only",
    )

    prev_reg = eval_mod.CONDITION_REGISTRY
    prev_schema = dict(ruleset_mod.CONDITION_SCHEMA)
    try:
        eval_mod.CONDITION_REGISTRY = local  # type: ignore[misc]
        ruleset_mod.CONDITION_SCHEMA[key] = bool
        rs = parse_ruleset(
            {
                "id": "T3C_TEST",
                "version": "1",
                "direction": "LONG",
                "conditions": {key: True},
            }
        )
        assert rs.condition_group.all_of[key] is True
        series = build_feature_series(_make_candles(40, seed=3))
        assert all(
            _condition_holds(bar, key, True, Direction.LONG) for bar in series.bars
        )
    finally:
        eval_mod.CONDITION_REGISTRY = prev_reg  # type: ignore[misc]
        ruleset_mod.CONDITION_SCHEMA.clear()
        ruleset_mod.CONDITION_SCHEMA.update(prev_schema)


def test_builtins_do_not_violate_allowed_values():
    """Parse all builtins — enum validation must not reject catalog values."""
    from app.strategy_lab.catalog import list_builtin_rulesets

    for rs in list_builtin_rulesets():
        # Re-parse from dict to exercise _coerce_leaf / allowed_values.
        parse_ruleset(rs.to_dict())
