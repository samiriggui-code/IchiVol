"""Ratchet: no direct compute_<registry_id> outside app/indicators/.

After T1e, ALLOWED_DIRECT_CALLERS is empty — any import/call of a registry
``compute_<id>`` under ``app/`` (except ``app/indicators/``) fails this test.

Exceptions (not registry indicators — do not trip the scan):
  - ``compute_oi_funding`` — external OI/funding streams, deliberately
    outside REGISTRY (see registry module docstring).
  - ``compute_projected_kumo`` — display-only chart helper; guarded by
    ``tests/indicators/test_projected_kumo.py``.
"""

from __future__ import annotations

import ast
from pathlib import Path

from app.indicators.registry import REGISTRY

_APP = Path(__file__).resolve().parents[2] / "app"

# Empty after T1e — no remaining allowlisted bypasses.
ALLOWED_DIRECT_CALLERS: frozenset[str] = frozenset()


def _registry_compute_names() -> set[str]:
    return {f"compute_{iid}" for iid in REGISTRY.ids()}


def _scan_direct_callers() -> dict[str, set[str]]:
    """relpath → set of compute_* names referenced (import or call)."""
    names = _registry_compute_names()
    found: dict[str, set[str]] = {}
    for path in _APP.rglob("*.py"):
        try:
            rel = path.relative_to(_APP).as_posix()
        except ValueError:
            continue
        if rel.startswith("indicators/") or rel == "indicators":
            continue
        src = path.read_text(encoding="utf-8")
        if not any(n in src for n in names):
            continue
        try:
            tree = ast.parse(src)
        except SyntaxError:
            found[rel] = {n for n in names if n in src}
            continue
        confirmed: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    if alias.name in names:
                        confirmed.add(alias.name)
            elif isinstance(node, ast.Name) and node.id in names:
                confirmed.add(node.id)
            elif isinstance(node, ast.Attribute) and node.attr in names:
                confirmed.add(node.attr)
        if confirmed:
            found[rel] = confirmed
    return found


def test_registry_direct_call_ratchet_empty():
    found = _scan_direct_callers()
    assert found == {}, (
        "direct compute_<registry_id> outside app/indicators/ is forbidden "
        f"(T1e empty allowlist):\n"
        + "\n".join(f"  {p}: {sorted(v)}" for p, v in sorted(found.items()))
    )


def test_allowed_list_is_empty():
    assert ALLOWED_DIRECT_CALLERS == frozenset()
