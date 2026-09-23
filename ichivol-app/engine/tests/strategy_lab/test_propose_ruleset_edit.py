"""T3d — propose_ruleset_edit + condition catalog."""

from __future__ import annotations

import pytest

from app.strategy_lab.catalog import get_builtin_ruleset, list_builtin_rulesets
from app.strategy_lab.propose_edit import condition_catalog, propose_ruleset_edit
from app.strategy_lab.ruleset import parse_ruleset


def test_condition_catalog_covers_registry():
    cat = condition_catalog()
    assert len(cat) >= 20
    keys = {c["key"] for c in cat}
    assert "rvol_min" in keys
    assert "price_above_kumo" in keys
    for c in cat:
        assert "value_type" in c
        assert "indicator_id" in c
        assert "description" in c


def test_propose_set_leaf_rvol():
    base = list_builtin_rulesets()[0]
    out = propose_ruleset_edit(
        base_ruleset_id=base.id,
        patch={"op": "set_leaf", "group": "all", "key": "rvol_min", "value": 2.5},
    )
    assert out["status"] == "proposed"
    assert "never auto-applied" in out["disclaimer"].lower()
    rs = parse_ruleset(out["ruleset"])
    assert rs.conditions.get("rvol_min") == 2.5 or (
        rs.condition_group.all_of.get("rvol_min") == 2.5
    )
    assert out["ruleset"]["id"].endswith("__proposed") or out["ruleset"]["id"] != base.id


def test_propose_unknown_key_fails():
    base = list_builtin_rulesets()[0]
    with pytest.raises(ValueError, match="unknown condition"):
        propose_ruleset_edit(
            base_ruleset_id=base.id,
            patch={"op": "set_leaf", "key": "not_a_real_key", "value": True},
        )


def test_propose_full_ruleset_candidate():
    base = get_builtin_ruleset(list_builtin_rulesets()[0].id)
    cand = base.to_dict()
    cand["id"] = "IV_LAB_PROPOSED_001"
    cand["stop_atr"] = 1.5
    out = propose_ruleset_edit(ruleset=cand)
    assert out["status"] == "proposed"
    assert out["ruleset"]["id"] == "IV_LAB_PROPOSED_001"
    assert out["ruleset"]["stop_atr"] == 1.5
    assert out["base_id"] is None


def test_propose_unset_and_direction():
    base = list_builtin_rulesets()[0]
    out = propose_ruleset_edit(
        base_ruleset_id=base.id,
        patches=[
            {"op": "set_direction", "direction": "SHORT"},
            {"op": "set_stop_atr", "value": 1.25},
        ],
    )
    assert out["ruleset"]["direction"] == "SHORT"
    assert out["ruleset"]["stop_atr"] == 1.25
    assert out["diff"]["top_level"]["direction"]["to"] == "SHORT"


def test_propose_does_not_mutate_builtin():
    base = get_builtin_ruleset(list_builtin_rulesets()[0].id)
    before = base.to_dict()
    propose_ruleset_edit(
        base_ruleset_id=base.id,
        patch={"op": "set_target_atr", "value": 9.0},
    )
    again = get_builtin_ruleset(base.id).to_dict()
    assert again == before
