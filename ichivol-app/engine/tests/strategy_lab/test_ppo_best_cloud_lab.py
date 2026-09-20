"""T-EXP — PPO / BEST Cloud wired into Strategy Lab only (no production path)."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.agents.types import Direction
from app.indicators.best_cloud import compute_best_cloud
from app.indicators.ppo import PpoCross, compute_ppo
from app.strategy_lab.ablation import (
    ABLATION_LADDERS,
    PPO_ABLATION_LAYERS,
    build_cumulative_rulesets,
    build_leave_one_layer_out_rulesets,
    run_ablation_on_candles,
)
from app.strategy_lab.catalog import get_builtin_ruleset, list_builtin_rulesets
from app.strategy_lab.evaluator import bar_matches
from app.strategy_lab.features import build_feature_series
from app.strategy_lab.ruleset import parse_ruleset
from tests.indicators.test_ichimoku_lookahead import _make_candles

APP = Path(__file__).resolve().parents[2] / "app"

NEW_FIELDS = (
    "ppo",
    "ppo_signal",
    "ppo_histogram",
    "ppo_above_signal",
    "ppo_below_signal",
    "ppo_above_zero",
    "ppo_below_zero",
    "ppo_histogram_rising",
    "ppo_histogram_falling",
    "ppo_signal_cross_bullish",
    "ppo_signal_cross_bearish",
    "ppo_cross_age_bullish",
    "ppo_cross_age_bearish",
    "ppo_momentum",
    "best_cloud_trend",
    "best_cloud_bullish",
    "best_cloud_bearish",
    "best_cloud_inside",
    "best_cloud_cross_bullish",
    "best_cloud_cross_bearish",
    "best_cloud_cross_age_bullish",
    "best_cloud_cross_age_bearish",
    "best_cloud_distance_pct",
)


def test_feature_bar_new_fields_are_causal():
    candles = _make_candles(260, seed=51)
    full = build_feature_series(candles)
    for t in (30, 60, 100, 180, 259):
        trunc = build_feature_series(candles[:t])
        for name in NEW_FIELDS:
            assert getattr(trunc.bars[-1], name) == getattr(full.bars[t - 1], name), (
                f"FeatureBar.{name} changed when future candles were added (T={t})"
            )


def test_feature_bar_mirrors_indicator_states():
    candles = _make_candles(260, seed=52)
    fs = build_feature_series(candles)
    ppo = compute_ppo(candles)
    cloud = compute_best_cloud(candles)
    assert fs.ppo == ppo and fs.best_cloud == cloud
    for i in (40, 120, 259):
        assert fs.bars[i].ppo == ppo[i].ppo
        assert fs.bars[i].ppo_momentum == ppo[i].momentum.value
        assert fs.bars[i].best_cloud_trend == cloud[i].trend.value


def test_ruleset_accepts_new_keys_and_rejects_bad_enum():
    rs = parse_ruleset(
        {
            "id": "IV_T",
            "direction": "LONG",
            "conditions": {
                "ppo_momentum": "strong_bullish",
                "best_cloud_trend": "BULLISH",
                "ppo_cross_age_max": 3,
                "ppo_min": 0.0,
            },
        }
    )
    assert rs.conditions["ppo_momentum"] == "STRONG_BULLISH"
    with pytest.raises(ValueError):
        parse_ruleset(
            {"id": "X", "direction": "LONG", "conditions": {"ppo_momentum": "MOON"}}
        )
    with pytest.raises(ValueError):
        parse_ruleset(
            {"id": "X", "direction": "LONG", "conditions": {"ppo_typo": True}}
        )


def test_evaluator_matches_new_conditions():
    candles = _make_candles(300, seed=53)
    fs = build_feature_series(candles)

    def rs(cond, direction="LONG"):
        return parse_ruleset({"id": "T", "direction": direction, "conditions": cond})

    momentum = rs({"ppo_momentum": "STRONG_BULLISH"})
    cloud = rs({"best_cloud_trend": "BULLISH"})
    above_zero_rising = rs({"ppo_above_zero": True, "ppo_histogram_rising": True})
    n_mom = n_cloud = 0
    for b in fs.bars:
        assert bar_matches(b, momentum) == (b.ppo_momentum == "STRONG_BULLISH")
        assert bar_matches(b, cloud) == b.best_cloud_bullish
        assert bar_matches(b, above_zero_rising) == (
            b.ppo_above_zero and b.ppo_histogram_rising
        )
        n_mom += bar_matches(b, momentum)
        n_cloud += bar_matches(b, cloud)
    assert n_mom > 0 and n_cloud > 0, "synthetic data should exercise both"


def test_cross_age_is_direction_aware():
    candles = _make_candles(300, seed=54)
    fs = build_feature_series(candles)
    states = fs.ppo
    long_rs = parse_ruleset(
        {"id": "L", "direction": "LONG", "conditions": {"ppo_cross_age_max": 2}}
    )
    short_rs = parse_ruleset(
        {"id": "S", "direction": "SHORT", "conditions": {"ppo_cross_age_max": 2}}
    )
    for b, st in zip(fs.bars, states):
        recent = st.bars_since_signal_cross is not None and st.bars_since_signal_cross <= 2
        assert bar_matches(b, long_rs) == (recent and st.last_signal_cross == PpoCross.BULLISH)
        assert bar_matches(b, short_rs) == (recent and st.last_signal_cross == PpoCross.BEARISH)


def test_catalog_has_t_exp_rulesets():
    ids = {r.id for r in list_builtin_rulesets()}
    for rid in (
        "IV_EXP_PPO_ICHI_RVOL_001",
        "IV_EXP_BESTCLOUD_ICHI_RVOL_001",
        "IV_EXP_PPO_BESTCLOUD_ICHI_RVOL_BOS_001",
    ):
        assert rid in ids
    assert get_builtin_ruleset("IV_EXP_PPO_ICHI_RVOL_001").meta["experiment"] == "T-EXP"
    # baseline ruleset untouched
    assert "ppo_momentum" not in get_builtin_ruleset("IV_ICHIMOKU_RVOL_LONG_001").conditions


def test_ppo_ladder_is_cumulative_a_to_d():
    assert ABLATION_LADDERS["ppo"] is PPO_ABLATION_LAYERS
    sets = build_cumulative_rulesets(PPO_ABLATION_LAYERS, direction=Direction.LONG)
    assert [s.meta["ablation_label"] for s in sets] == [
        "A_ICHIMOKU",
        "B_RVOL",
        "C_BOS",
        "D_PPO",
        "E_BEST_CLOUD",
    ]
    assert "ppo_momentum" not in sets[2].conditions
    assert "ppo_momentum" in sets[3].conditions
    assert "best_cloud_trend" not in sets[3].conditions
    assert "best_cloud_trend" in sets[4].conditions


def test_leave_one_layer_out_drops_whole_layer():
    sets = build_leave_one_layer_out_rulesets(PPO_ABLATION_LAYERS)
    by_label = {s.meta["ablation_label"]: s for s in sets}
    assert set(by_label) == {
        "FULL",
        "NO_A_ICHIMOKU",
        "NO_B_RVOL",
        "NO_C_BOS",
        "NO_D_PPO",
        "NO_E_BEST_CLOUD",
    }
    no_ichi = by_label["NO_A_ICHIMOKU"].conditions
    assert "price_above_kumo" not in no_ichi and "tk_cross_age_max" not in no_ichi
    assert "rvol_min" in no_ichi
    no_ppo = by_label["NO_D_PPO"].conditions
    assert "ppo_momentum" not in no_ppo and "best_cloud_trend" in no_ppo
    assert set(by_label["FULL"].conditions) == set(no_ichi) | {
        "price_above_kumo",
        "tenkan_above_kijun",
        "tk_cross_age_max",
    }


def test_leave_one_layer_out_rejects_overlapping_keys():
    with pytest.raises(ValueError):
        build_leave_one_layer_out_rulesets(
            [("A", {"rvol_min": 1.5}), ("B", {"rvol_min": 2.0})]
        )


def test_run_ablation_ppo_ladder_and_layer_out():
    candles = _make_candles(420, seed=55)
    cum = run_ablation_on_candles(
        candles,
        symbol="TEST",
        timeframe="1h",
        mode="cumulative",
        layers=PPO_ABLATION_LAYERS,
        persist=False,
    )
    assert [s.label for s in cum.steps][-2:] == ["D_PPO", "E_BEST_CLOUD"]
    assert len(cum.deltas) == 4
    assert cum.deltas[-2].added_conditions == ["ppo_momentum"]
    # Cumulative ladder can only shrink the matching-bar set.
    n = [s.study.n_matching_bars for s in cum.steps]
    assert n == sorted(n, reverse=True)

    loo = run_ablation_on_candles(
        candles,
        symbol="TEST",
        timeframe="1h",
        mode="leave_one_layer_out",
        layers=PPO_ABLATION_LAYERS,
        persist=False,
    )
    assert loo.steps[0].label == "FULL" and len(loo.steps) == 6
    assert len(loo.deltas) == 5
    full_n = loo.steps[0].study.n_matching_bars
    # Dropping a layer can only widen (never shrink) the matching-bar set.
    assert all(s.study.n_matching_bars >= full_n for s in loo.steps[1:])


@pytest.mark.parametrize(
    "rel",
    [
        "decision/pipeline.py",
        "decision/combiner.py",
        "screener/service.py",
        "paper/engine.py",
        "paper/gates.py",
        "evidence/context.py",
        "agent_channel",
    ],
)
def test_production_path_does_not_import_experimental_features(rel):
    """T-EXP guard: PPO / BEST Cloud must not reach decisions, paper or Claude."""
    target = APP / rel
    files = list(target.rglob("*.py")) if target.is_dir() else [target]
    assert files
    for f in files:
        src = f.read_text(encoding="utf-8-sig")
        for needle in ("indicators.ppo", "indicators.best_cloud", "best_cloud", "compute_ppo"):
            assert needle not in src, f"{f} references experimental feature {needle!r}"
