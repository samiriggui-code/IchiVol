"""Ratchet: direct compute_<id> calls outside app/indicators/ must shrink.

After T1c, strategy_lab/features.py goes through REGISTRY. Remaining
callers stay on ALLOWED_DIRECT_CALLERS until T1d migrates them.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

from app.indicators.registry import REGISTRY

_APP = Path(__file__).resolve().parents[2] / "app"

# Frozen allowlist of modules (path relative to app/) that still call compute_*
# for registry ids directly. Remove an entry only when that module no longer
# has a direct call — the test fails both on new offenders and on stale entries.
ALLOWED_DIRECT_CALLERS: frozenset[str] = frozenset(
    {
        # T1e remaining bypasses (live/backtest/lab/API glue):
        "api/routes.py",
        "agent_channel/commands.py",
        "backtest/experiments.py",
        "strategy_lab/regime.py",
        "synthetic/validation.py",
        "structure/atr_utils.py",
    }
)

# Scan target excludes app/indicators/ (definitions + registry wrappers live there).
_SCAN_ROOTS = (
    "strategy_lab",
    "screener",
    "backtest",
    "synthetic",
    "context",
    "api",
    "evidence",
    "structure",
    "agents",
    "agent_channel",
    "decision",
    "fibonacci",
    "market_data",
    "paper",
    "shadow",
)


def _registry_compute_names() -> set[str]:
    """Map registry id → compute_<id> name used in source (id may contain underscores)."""
    return {f"compute_{iid}" for iid in REGISTRY.ids()}


def _scan_direct_callers() -> dict[str, set[str]]:
    """relpath → set of compute_* names referenced (import or call)."""
    names = _registry_compute_names()
    found: dict[str, set[str]] = {}
    for root_name in _SCAN_ROOTS:
        root = _APP / root_name
        if not root.is_dir():
            continue
        for path in root.rglob("*.py"):
            rel = str(path.relative_to(_APP))
            src = path.read_text(encoding="utf-8")
            hits: set[str] = set()
            # Fast path: name must appear as a token.
            for name in names:
                if name not in src:
                    continue
                hits.add(name)
            if not hits:
                continue
            # Confirm via AST (import from / Name / Attribute).
            try:
                tree = ast.parse(src)
            except SyntaxError:
                found[rel] = hits
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


def test_registry_direct_call_ratchet():
    found = _scan_direct_callers()
    # Never allow features.py to call compute_* directly after T1c.
    assert "strategy_lab/features.py" not in found, (
        "strategy_lab/features.py must use REGISTRY.compute_many, not compute_*"
    )

    allow = set(ALLOWED_DIRECT_CALLERS)
    offenders = sorted(set(found) - allow)
    stale = sorted(allow - set(found))

    assert not offenders, (
        "new direct compute_* callers outside allowlist (migrate or add deliberately):\n"
        + "\n".join(f"  {p}: {sorted(found[p])}" for p in offenders)
    )
    assert not stale, (
        "ALLOWED_DIRECT_CALLERS entries no longer call compute_* — remove them:\n"
        + "\n".join(f"  {p}" for p in stale)
    )


def test_allowed_list_has_no_features():
    assert "strategy_lab/features.py" not in ALLOWED_DIRECT_CALLERS
