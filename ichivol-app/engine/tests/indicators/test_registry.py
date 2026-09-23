"""Tests for IndicatorRegistry — parity, warmup, anti-lookahead, validation."""

from __future__ import annotations

import json
from dataclasses import dataclass

import pytest

from app.indicators.ichimoku import compute_ichimoku
from app.indicators.registry import (
    REGISTRY,
    IndicatorCategory,
    IndicatorDefinition,
    IndicatorRegistry,
    InvalidParamsError,
    UnknownIndicatorError,
    Visualization,
)
from app.indicators.rvol import compute_rvol
from tests.indicators.test_ichimoku_lookahead import _make_candles

ALL_IDS = REGISTRY.ids()


@pytest.mark.parametrize("indicator_id", ALL_IDS)
def test_primary_output_in_outputs(indicator_id: str):
    definition = REGISTRY.get(indicator_id)
    assert definition.primary_output in definition.outputs()


@pytest.mark.parametrize("indicator_id", ALL_IDS)
def test_warmup_at_least_one(indicator_id: str):
    assert REGISTRY.get(indicator_id).warmup() >= 1


@pytest.mark.parametrize("indicator_id", ALL_IDS)
def test_one_state_per_candle(indicator_id: str):
    candles = _make_candles(80)
    states = REGISTRY.compute(indicator_id, candles)
    assert len(states) == len(candles)


@pytest.mark.parametrize("indicator_id", ALL_IDS)
def test_no_lookahead(indicator_id: str):
    candles = _make_candles(220)
    full = REGISTRY.compute(indicator_id, candles)
    for t in (5, 30, 79, 120, 219):
        truncated = REGISTRY.compute(indicator_id, candles[:t])
        assert truncated[-1] == full[t - 1], f"{indicator_id} leaked at t={t}"


def test_registry_matches_compute_ichimoku():
    candles = _make_candles(120)
    assert REGISTRY.compute("ichimoku", candles) == compute_ichimoku(candles)


def test_registry_matches_compute_rvol():
    candles = _make_candles(120)
    assert REGISTRY.compute("rvol", candles) == compute_rvol(candles)


def test_override_changes_warmup():
    base = REGISTRY.get("rvol").warmup()
    overridden = REGISTRY.get("rvol").warmup({"primary_window": base + 7})
    assert overridden == base + 7


def test_unknown_param_rejected():
    with pytest.raises(InvalidParamsError):
        REGISTRY.get("atr").build_params({"not_a_real_param": 1})


def test_nested_params_override_builds_dataclass():
    built = REGISTRY.get("location").build_params(
        {"volume_profile": {"num_bins": 10}, "vwap_window": 15}
    )
    assert built.vwap_window == 15
    assert built.volume_profile.num_bins == 10
    # Unspecified nested fields keep defaults
    assert built.volume_profile.lookback == 100
    candles = _make_candles(120)
    states = REGISTRY.compute("location", candles, built)
    assert len(states) == len(candles)


def test_nested_params_unknown_key_raises():
    with pytest.raises(InvalidParamsError, match=r"location\.volume_profile\.foo"):
        REGISTRY.get("location").build_params({"volume_profile": {"foo": 1}})


def test_ppo_fast_gt_slow_rejected():
    with pytest.raises(InvalidParamsError):
        REGISTRY.get("ppo").build_params({"fast": 30, "slow": 12})


def test_unknown_id_rejected():
    with pytest.raises(UnknownIndicatorError):
        REGISTRY.get("not_an_indicator")


def test_duplicate_register_rejected():
    local = IndicatorRegistry()
    definition = REGISTRY.get("rsi")
    local.register(
        IndicatorDefinition(
            id="rsi_probe",
            name="probe",
            category=IndicatorCategory.MOMENTUM,
            params_cls=definition.params_cls,
            compute_fn=definition.compute_fn,
            warmup_fn=definition.warmup_fn,
            primary_output=definition.primary_output,
            visualization=Visualization.PANE,
        )
    )
    with pytest.raises(ValueError, match="duplicate"):
        local.register(
            IndicatorDefinition(
                id="rsi_probe",
                name="probe2",
                category=IndicatorCategory.MOMENTUM,
                params_cls=definition.params_cls,
                compute_fn=definition.compute_fn,
                warmup_fn=definition.warmup_fn,
                primary_output=definition.primary_output,
                visualization=Visualization.PANE,
            )
        )


def test_catalog_json_serializable():
    payload = REGISTRY.catalog()
    dumped = json.dumps(payload)
    assert isinstance(json.loads(dumped), list)
    assert {row["id"] for row in payload} == set(ALL_IDS)


def test_negative_control_leaky_indicator_fails_lookahead_check():
    """An indicator that reads close[i+1] must fail the truncation check."""

    @dataclass(frozen=True)
    class _LeakyParams:
        unused: int = 1

    @dataclass(frozen=True)
    class _LeakyState:
        time: int
        value: float

    def _leaky_compute(candles, params: _LeakyParams):
        out: list[_LeakyState] = []
        for i, c in enumerate(candles):
            nxt = candles[i + 1].close if i + 1 < len(candles) else c.close
            out.append(_LeakyState(time=c.time, value=c.close + nxt))
        return out

    leaky = IndicatorDefinition(
        id="leaky",
        name="Leaky",
        category=IndicatorCategory.STATISTICAL,
        params_cls=_LeakyParams,
        compute_fn=_leaky_compute,
        warmup_fn=lambda p: 1,
        primary_output="value",
        visualization=Visualization.NONE,
    )

    candles = _make_candles(80)
    full = leaky.compute(candles)
    # At t=40 the truncated window no longer sees candles[40], so state differs.
    t = 40
    truncated = leaky.compute(candles[:t])
    assert truncated[-1] != full[t - 1]


def test_compute_many_resolves_deps_once():
    candles = _make_candles(60)
    out = REGISTRY.compute_many(
        ["ichimoku_analytics", "ichimoku", "atr"],
        candles,
    )
    assert set(out) == {"ichimoku_analytics", "ichimoku", "atr"}
    assert out["ichimoku_analytics"] == REGISTRY.compute("ichimoku_analytics", candles)


def test_compute_many_cycle_raises():
    from app.indicators.registry import DependencyCycleError

    local = IndicatorRegistry()

    @dataclass(frozen=True)
    class _P:
        x: int = 1

    def _leaf(candles, params):
        return []

    def _a(candles, params, deps):
        return []

    def _b(candles, params, deps):
        return []

    local.register(
        IndicatorDefinition(
            id="a",
            name="A",
            category=IndicatorCategory.TREND,
            params_cls=_P,
            compute_fn=_a,
            warmup_fn=lambda p: 1,
            primary_output="x",
            visualization=Visualization.NONE,
            depends_on=("b",),
        )
    )
    local.register(
        IndicatorDefinition(
            id="b",
            name="B",
            category=IndicatorCategory.TREND,
            params_cls=_P,
            compute_fn=_b,
            warmup_fn=lambda p: 1,
            primary_output="x",
            visualization=Visualization.NONE,
            depends_on=("a",),
        )
    )
    with pytest.raises(DependencyCycleError):
        local.compute_many(["a"], [])


def test_dependent_warmup_includes_deps():
    analytics_w = REGISTRY.get("ichimoku_analytics").warmup()
    assert analytics_w >= REGISTRY.get("ichimoku").warmup()
    assert analytics_w >= REGISTRY.get("atr").warmup()
    assert REGISTRY.get("location").warmup() >= REGISTRY.get("structure").warmup()
    assert REGISTRY.get("wyckoff").warmup() >= REGISTRY.get("donchian").warmup()
