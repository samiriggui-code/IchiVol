"""T11a-bis — production import guard for decision pipeline + combiner.

Walks the transitive import graph from ``decision.pipeline`` and
``decision.combiner``. Fails if either reaches:

- ``app.strategy_lab.lab_context`` (Lab observation must not leak into live)
- any ``app.indicators.<id>`` whose registry ``FeatureStatus`` is not PRODUCTION

``oi_funding`` is allowlisted (futures streams, intentionally outside REGISTRY).
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

import pytest

from app.indicators.registry import REGISTRY, FeatureStatus

APP = Path(__file__).resolve().parents[2] / "app"
SEEDS = (
    APP / "decision" / "pipeline.py",
    APP / "decision" / "combiner.py",
)

# Not in REGISTRY; pipeline may import it for futures overlays.
_ALLOWLIST_INDICATOR_MODULES = frozenset(
    {
        "app.indicators.oi_funding",
        "app.indicators.ichimoku",  # Candle + types shared widely
        "app.indicators.registry",
    }
)


def _module_name_for_path(path: Path) -> str | None:
    try:
        rel = path.resolve().relative_to(APP.resolve())
    except ValueError:
        return None
    if rel.suffix != ".py":
        return None
    parts = list(rel.with_suffix("").parts)
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return "app." + ".".join(parts)


def _resolve_import(module: str, name: str, level: int) -> str | None:
    if level == 0:
        return name
    # Relative: climb from module's package.
    pkg_parts = module.split(".")[:-1]  # drop module leaf
    if level > len(pkg_parts) + 1:
        return None
    base = pkg_parts[: len(pkg_parts) - (level - 1)]
    if name:
        return ".".join(base + name.split("."))
    return ".".join(base) if base else None


def _imports_from_file(path: Path, module: str) -> set[str]:
    src = path.read_text(encoding="utf-8-sig")
    tree = ast.parse(src, filename=str(path))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                found.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            mod = _resolve_import(module, node.module or "", node.level)
            if mod:
                found.add(mod)
                # also record submodule leaves imported from package
                for alias in node.names:
                    if alias.name != "*":
                        found.add(f"{mod}.{alias.name}")
    return found


def _path_for_module(mod: str) -> Path | None:
    if not mod.startswith("app."):
        return None
    rel = Path(*mod.split(".")[1:])
    py = APP / rel.with_suffix(".py")
    if py.exists():
        return py
    init = APP / rel / "__init__.py"
    if init.exists():
        return init
    return None


def _transitive_app_imports(seeds: tuple[Path, ...]) -> set[str]:
    seen_mods: set[str] = set()
    queue: list[Path] = list(seeds)
    while queue:
        path = queue.pop()
        mod = _module_name_for_path(path)
        if mod is None or mod in seen_mods:
            continue
        seen_mods.add(mod)
        for dep in _imports_from_file(path, mod):
            # Normalize attribute imports: app.foo.Bar → try app.foo
            candidates = [dep]
            parts = dep.split(".")
            for i in range(len(parts) - 1, 1, -1):
                candidates.append(".".join(parts[:i]))
            for c in candidates:
                if not c.startswith("app."):
                    continue
                if c in seen_mods:
                    continue
                p = _path_for_module(c)
                if p is not None:
                    queue.append(p)
                    break
    return seen_mods


def test_pipeline_and_combiner_never_import_lab_context():
    mods = _transitive_app_imports(SEEDS)
    offenders = sorted(m for m in mods if m == "app.strategy_lab.lab_context" or m.startswith("app.strategy_lab.lab_context."))
    assert offenders == [], f"live decision path imports lab_context: {offenders}"


def test_pipeline_and_combiner_only_production_indicators():
    mods = _transitive_app_imports(SEEDS)
    bad: list[str] = []
    for m in sorted(mods):
        if not m.startswith("app.indicators."):
            continue
        if m in _ALLOWLIST_INDICATOR_MODULES:
            continue
        # app.indicators.<leaf> or deeper
        leaf = m.split(".")[2] if len(m.split(".")) >= 3 else None
        if leaf is None or leaf.startswith("_"):
            continue
        # Skip non-registry helper modules (params living beside compute)
        defn = REGISTRY.get(leaf) if leaf in {d.id for d in REGISTRY.all()} else None
        if defn is None:
            # Unknown indicator module under app.indicators — only fail if it
            # matches a known registry id package file.
            continue
        if defn.status is not FeatureStatus.PRODUCTION:
            bad.append(f"{m} status={defn.status.value}")
    assert bad == [], f"non-PRODUCTION indicators reachable from pipeline/combiner: {bad}"


def test_seed_files_exist():
    for p in SEEDS:
        assert p.is_file(), p
