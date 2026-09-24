"""T12e — ADN IchiVol matrix A→F (unit tests)."""

from __future__ import annotations

from app.strategy_lab.ablation import ABLATION_LADDERS
from app.strategy_lab.adn_ichivol import (
    ADN_LADDER_NAME,
    LiveScreenerSettings,
    adn_absolute_models,
    adn_cumulative_delta_layers,
    adn_model_c_conditions,
    map_t9g_to_verdict,
    run_adn_matrix_on_candles,
)
from tests.indicators.test_ichimoku_lookahead import _make_candles


def test_live_settings_production_defaults_match_resolve_ts():
    s = LiveScreenerSettings.production_defaults()
    assert s.rvol_significant == 1.5
    assert s.rvol_low == 0.7
    assert s.rvol_strong == 2.0
    assert s.rvol_anomaly == 3.0
    assert s.ichi_tenkan == 9
    assert s.source == "production_defaults"
    rp = s.rvol_params()
    assert rp.significant_threshold == 1.5
    assert rp.primary_window == 20


def test_live_settings_from_mapping_overrides_rvol():
    s = LiveScreenerSettings.from_mapping(
        {"rvolSignificant": 2.0, "rvolLow": 0.5},
        source="api_settings",
    )
    assert s.rvol_significant == 2.0
    assert s.rvol_low == 0.5
    assert s.source == "api_settings"
    layers = adn_cumulative_delta_layers(s)
    assert layers[1][0] == "B_RVOL"
    assert layers[1][1]["rvol_min"] == 2.0
    assert adn_model_c_conditions(s)["rvol_min"] == 2.0


def test_map_t9g_verdicts():
    assert map_t9g_to_verdict("review_candidate") == "KEEP"
    assert map_t9g_to_verdict("inconclusive") == "RESEARCH"
    assert map_t9g_to_verdict("reject") == "REJECT"
    assert map_t9g_to_verdict("promote") == "RESEARCH"  # never promote


def test_adn_ladder_registered():
    assert ADN_LADDER_NAME in ABLATION_LADDERS
    layers = ABLATION_LADDERS[ADN_LADDER_NAME]
    labels = [lab for lab, _ in layers]
    assert labels == ["A_ICHIMOKU", "B_RVOL", "D_STRUCTURE", "E_LOCATION", "F_REGIME"]


def test_adn_absolute_models_include_c_and_catalog():
    models = adn_absolute_models()
    assert set(models) >= {"A", "B", "C", "D", "E", "F", "ICHIVOL_CURRENT"}
    assert "bos_bullish" in models["C"].conditions
    assert "rvol_min" in models["C"].conditions
    assert "price_above_kumo" not in models["C"].conditions
    assert "bos_bullish" in models["D"].conditions
    assert "price_above_kumo" in models["D"].conditions
    assert "location_stage_pass" in models["E"].conditions
    assert "regime_stage_pass" in models["F"].conditions


def test_run_adn_matrix_on_synthetic():
    candles = _make_candles(320, seed=42)
    settings = LiveScreenerSettings.from_mapping(
        {"rvolSignificant": 1.2},
        source="test_override",
    )
    report = run_adn_matrix_on_candles(
        candles,
        symbol="BTCUSDT",
        timeframe="1h",
        settings=settings,
        train_bars=80,
        test_bars=30,
        step_bars=30,
        warmup_bars=52,
        min_oos_trades=1,
        with_references=True,
    )
    assert report.n_bars == 320
    assert report.settings.rvol_significant == 1.2
    assert report.ablation_oos is not None
    assert report.references is not None
    assert len(report.references.baselines) == 3
    models = {r.model for r in report.rows}
    assert {"A", "B", "C", "D", "E", "F"} <= models
    for row in report.rows:
        assert row.verdict in ("KEEP", "RESEARCH", "REJECT")
    payload = report.to_dict()
    assert payload["settings"]["source"] == "test_override"
    assert "promote" not in payload["disclaimer"].lower() or "not a promotion" in payload[
        "disclaimer"
    ].lower()


def test_stage_pass_enum_coercion_accepts_lowercase():
    from app.strategy_lab.ruleset import parse_ruleset

    rs = parse_ruleset(
        {
            "id": "IV_TEST_STAGE",
            "version": "1",
            "direction": "LONG",
            "conditions": {
                "location_stage_pass": "pass",
                "regime_stage_pass": "PASS",
            },
            "entry": "next_open",
            "stop_atr": 1.0,
            "target_atr": 2.0,
        }
    )
    assert rs.conditions["location_stage_pass"] == "pass"
    assert rs.conditions["regime_stage_pass"] == "pass"


def test_empty_engine_paths_untouched_marker():
    """Sanity: this module must not import live decision/screener open paths."""
    import app.strategy_lab.adn_ichivol as mod

    src = open(mod.__file__, encoding="utf-8").read()
    assert "app.decision.pipeline" not in src or "live_parity" in src
    assert "app.screener" not in src
    assert "app.paper" not in src
    assert "app.brokerage" not in src
