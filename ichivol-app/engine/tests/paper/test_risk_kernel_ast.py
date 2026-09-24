"""T13b — AST ratchet: all paper opens funnel through Risk Kernel."""

from __future__ import annotations

import ast
from pathlib import Path

ENGINE_ROOT = Path(__file__).resolve().parents[2] / "app"

# Definitions / post-evaluate open / quote path / tests
_OPEN_CAPITAL_ALLOW = frozenset(
    {
        "paper/broker.py",
        "paper/engine.py",
        "brokerage/quote_paper.py",
    }
)


def _py_files() -> list[Path]:
    return sorted(ENGINE_ROOT.rglob("*.py"))


def test_open_capital_position_call_sites_allowlisted():
    offenders: list[str] = []
    for path in _py_files():
        rel = path.relative_to(ENGINE_ROOT).as_posix()
        if rel.startswith("paper/") and rel.endswith("test"):
            continue
        src = path.read_text(encoding="utf-8")
        try:
            tree = ast.parse(src, filename=str(path))
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            name = None
            if isinstance(node.func, ast.Name) and node.func.id == "open_capital_position":
                name = "open_capital_position"
            elif isinstance(node.func, ast.Attribute) and node.func.attr == "open_capital_position":
                name = "open_capital_position"
            if name is None:
                continue
            if rel in _OPEN_CAPITAL_ALLOW:
                continue
            offenders.append(f"{rel}:{node.lineno}")
    assert not offenders, (
        "open_capital_position must only be called from allowlisted modules "
        f"(post Risk Kernel). Offenders: {offenders}"
    )


def test_sync_position_calls_risk_kernel_evaluate():
    path = ENGINE_ROOT / "paper" / "engine.py"
    src = path.read_text(encoding="utf-8")
    assert "risk_kernel_evaluate" in src or "risk_kernel.evaluate" in src
    assert "from app.paper.risk_kernel import" in src
    # Opening entrypoints must remain in this module
    assert "def sync_auto_watchlist" in src
    assert "def open_user_confirmed" in src
    assert "def sync_position" in src


def test_paper_orders_open_uses_risk_kernel_refusal():
    path = ENGINE_ROOT / "api" / "paper_orders.py"
    src = path.read_text(encoding="utf-8")
    assert "risk_kernel_evaluate" in src or "risk_kernel" in src
    assert "def open_paper_position" in src or "open_user_confirmed" in src
