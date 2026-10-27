"""Inventaire figé de la technologie IchiVol (2026-10-27, portefeuille unique).

Demande du propriétaire : « fais gaffe aux indicateurs Fibonacci etc., faut pas me les virer ». Ce test échoue si un
indicateur du registre, une porte de filtre ou un moteur d'analyse disparaît. Ajouter un indicateur est libre ;
en retirer un oblige à modifier cette liste, donc à le décider explicitement.
"""

from __future__ import annotations

import importlib

import pytest

from app.indicators.registry import REGISTRY

FROZEN_INDICATORS = frozenset({
    "adx", "atr", "best_cloud", "cmf", "cvd", "donchian", "fvg", "ichimoku", "ichimoku_analytics", "impulse",
    "location", "obv", "ppo", "rsi", "rvol", "structure", "wyckoff",
})

# Méthodes hors registre utilisées par le moteur, Ève ou les écrans : chaque module doit rester importable et
# exposer sa fonction d'entrée.
FROZEN_METHODS = [
    ("app.fibonacci.gate", "apply_fibonacci_gate"),
    ("app.structure.gate", "apply_structure_gate"),
    ("app.context.gate", "apply_context_gate"),
    ("app.sessions.decision_windows", "decision_event_for_bar"),
    ("app.indicators.oi_funding", "compute_oi_funding"),
    ("app.decision.pipeline", "PipelineResult"),
    ("app.mtf.service", "clear_cache"),
    ("app.shadow.broker", "open_shadow"),
    ("app.eve.orchestrator", "evaluate_opportunity"),
    ("app.eve.modes", "synthesize_action"),
    ("app.jev.adapter", None),
]


def test_no_registry_indicator_disappears():
    missing = FROZEN_INDICATORS - set(REGISTRY.ids())
    assert not missing, f"indicateurs retirés du registre : {sorted(missing)}"


@pytest.mark.parametrize("module,attr", FROZEN_METHODS)
def test_analysis_methods_still_exist(module, attr):
    mod = importlib.import_module(module)
    if attr is not None:
        assert hasattr(mod, attr), f"{module}.{attr} a disparu"


def test_single_portfolio_still_runs_every_confirmation_filter():
    """Les filtres des comptes retirés (Tout combiné, Sessions) tournent sur le compte unique, en observation."""
    from app.paper.strategy_profiles import MAIN_PROFILE

    assert MAIN_PROFILE["structure_filter"] and set(MAIN_PROFILE["structure_detectors"]) == {"mvpp", "trendln"}
    assert MAIN_PROFILE["fibonacci_filter"] == "require_confluence"
    assert all(MAIN_PROFILE[k] for k in ("context_rsi", "context_cmf", "context_obv", "context_regime_hard"))
    assert MAIN_PROFILE["filters_mode"] == "observe"
    assert MAIN_PROFILE["decision_windows"] and MAIN_PROFILE["decision_windows_mode"] == "observe"
