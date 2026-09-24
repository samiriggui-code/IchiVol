"""T10a — FeatureStatus / FeatureSource on the indicator registry."""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from app.indicators.registry import (
    REGISTRY,
    FeatureStatus,
)
from app.indicators.structure import StructureParams

APP = Path(__file__).resolve().parents[2] / "app"

# Modules that constitute the "production path" (brief T10a).
PRODUCTION_PATHS = [
    APP / "decision" / "pipeline.py",
    APP / "decision" / "combiner.py",
    APP / "screener" / "service.py",
    APP / "paper" / "engine.py",
    APP / "paper" / "gates.py",
    APP / "evidence" / "context.py",
    APP / "agents" / "ichimoku_agent.py",
    APP / "agents" / "rvol_agent.py",
]

# Justifications (file:line anchors) — keep in sync with registry._build_registry docstring.
PRODUCTION_JUSTIFICATIONS: dict[str, str] = {
    "ichimoku": "app/agents/ichimoku_agent.py (REGISTRY.compute) → combiner + evidence/context",
    "rvol": "app/agents/rvol_agent.py (REGISTRY.compute) → combiner + pipeline participation",
    "atr": "app/decision/pipeline.py (AtrState) + screener/service.py + evidence/catalog.py",
    "adx": "app/decision/pipeline.py (AdxState) + screener/service.py",
    "cvd": "app/decision/pipeline.py (CvdState) + screener/service.py",
    "donchian": "app/decision/pipeline.py (DonchianState) + screener/service.py",
    "structure": "app/decision/pipeline.py (StructureState) + screener/service.py",
    "location": "app/decision/pipeline.py (LocationState) + screener/service.py",
}


def _string_literals(path: Path) -> set[str]:
    """Collect string constants from a Python file (AST)."""
    src = path.read_text(encoding="utf-8-sig")
    tree = ast.parse(src, filename=str(path))
    out: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            out.add(node.value)
    return out


def test_every_definition_exposes_t10a_fields():
    for d in REGISTRY.all():
        payload = d.describe()
        assert payload["status"] in {s.value for s in FeatureStatus}
        assert isinstance(payload["source"], dict)
        assert payload["source"]["kind"] in {"internal", "external"}
        assert isinstance(payload["confirmation_lag_bars"], int)
        assert payload["confirmation_lag_bars"] >= 0
        assert isinstance(payload["family"], str)
        assert isinstance(payload["experiment_refs"], list)


def test_ppo_and_best_cloud_are_rejected():
    assert REGISTRY.get("ppo").status is FeatureStatus.REJECTED
    assert REGISTRY.get("best_cloud").status is FeatureStatus.REJECTED
    src = REGISTRY.get("best_cloud").source
    assert src.kind == "external"
    assert "Daveatt" in src.author
    assert "AU4EZIb9" in src.url


def test_wyckoff_experimental_pending_claude():
    """README moteur: non promu — Cursor propose EXPERIMENTAL; Claude tranche."""
    assert REGISTRY.get("wyckoff").status is FeatureStatus.EXPERIMENTAL


def test_structure_confirmation_lag_matches_swing_lookback():
    d = REGISTRY.get("structure")
    assert d.confirmation_lag_bars == StructureParams().swing_lookback
    # Coherence with fractal right lookback used in compute_structure.
    assert d.confirmation_lag_bars == StructureParams().swing_lookback


def test_production_ids_are_production_status():
    for iid, why in PRODUCTION_JUSTIFICATIONS.items():
        d = REGISTRY.get(iid)
        assert d.status is FeatureStatus.PRODUCTION, f"{iid} should be PRODUCTION ({why})"


def test_production_paths_only_use_production_registry_ids():
    """Generalized guard (replaces tag-based experimental check for status).

    Collect registry ids appearing as string literals in production modules;
    each must be FeatureStatus.PRODUCTION.
    """
    registry_ids = set(REGISTRY.ids())
    used: set[str] = set()
    for path in PRODUCTION_PATHS:
        assert path.exists(), path
        used |= _string_literals(path) & registry_ids
        # Also catch REGISTRY.compute("id") via regex for safety.
        src = path.read_text(encoding="utf-8-sig")
        for m in re.finditer(r'REGISTRY\.compute(?:_many)?\(\s*\[?["\']([a-z_]+)["\']', src):
            used.add(m.group(1))
        for m in re.finditer(r'REGISTRY\.compute\(\s*["\']([a-z_]+)["\']', src):
            used.add(m.group(1))

    # Screener uses a list literal — covered by AST; assert we found the core set.
    assert "structure" in used or "ichimoku" in used or "rvol" in used

    for iid in sorted(used):
        d = REGISTRY.get(iid)
        assert d.status is FeatureStatus.PRODUCTION, (
            f"production path uses {iid!r} with status={d.status.value}"
        )


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
def test_production_path_does_not_import_rejected_features(rel):
    """Keep the historical PPO/BEST Cloud import ban (now aligned with REJECTED)."""
    target = APP / rel
    files = list(target.rglob("*.py")) if target.is_dir() else [target]
    assert files
    for f in files:
        src = f.read_text(encoding="utf-8-sig")
        for needle in ("indicators.ppo", "indicators.best_cloud", "best_cloud", "compute_ppo"):
            assert needle not in src, f"{f} references REJECTED feature {needle!r}"
