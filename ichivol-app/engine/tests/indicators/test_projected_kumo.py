"""Projected Kumo — display-only; never a feature input."""

from __future__ import annotations

import ast
from pathlib import Path

from app.indicators.ichimoku import IchimokuParams, compute_ichimoku, compute_projected_kumo
from tests.indicators.test_ichimoku_lookahead import _make_candles

_ENGINE_APP = Path(__file__).resolve().parents[2] / "app"
_FORBIDDEN_IMPORT_ROOTS = ("strategy_lab", "decision", "backtest", "screener", "evidence")


def test_projected_kumo_matches_displayed_senkou_when_future_bar_exists():
    candles = _make_candles(160)
    params = IchimokuParams()
    d = params.displacement
    states = compute_ichimoku(candles, params)
    proj = compute_projected_kumo(candles, params)

    # Rebuild source index → projection (same skip rules as the helper).
    from app.indicators.ichimoku import _donchian_mid

    expected_by_time: dict[int, tuple[float, float]] = {}
    n = len(candles)
    for i in range(n):
        tenkan = _donchian_mid(candles, i, params.tenkan)
        kijun = _donchian_mid(candles, i, params.kijun)
        sa = (tenkan + kijun) / 2 if tenkan is not None and kijun is not None else None
        sb = _donchian_mid(candles, i, params.senkou_b)
        if sa is None or sb is None or i + d >= n:
            continue
        expected_by_time[candles[i + d].time] = (sa, sb)
        assert states[i + d].senkou_a == sa
        assert states[i + d].senkou_b == sb

    for p in proj:
        t = int(p["time_projected"])
        if t not in expected_by_time:
            continue  # extrapolated beyond last bar
        sa, sb = expected_by_time[t]
        assert p["senkou_a"] == sa
        assert p["senkou_b"] == sb


def test_projected_kumo_never_imported_by_decision_paths():
    """Guard: display helper must not leak into lab / decision / backtest / evidence."""
    offenders: list[str] = []
    for root_name in _FORBIDDEN_IMPORT_ROOTS:
        root = _ENGINE_APP / root_name
        if not root.is_dir():
            continue
        for path in root.rglob("*.py"):
            src = path.read_text(encoding="utf-8")
            if "compute_projected_kumo" not in src:
                continue
            try:
                tree = ast.parse(src)
            except SyntaxError:
                offenders.append(str(path))
                continue
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module:
                    if "compute_projected_kumo" in (a.name for a in node.names):
                        offenders.append(str(path.relative_to(_ENGINE_APP.parent)))
                if isinstance(node, ast.Name) and node.id == "compute_projected_kumo":
                    offenders.append(str(path.relative_to(_ENGINE_APP.parent)))
    assert offenders == [], f"display-only import leak: {offenders}"


def test_projection_window_uses_warmup_history():
    """Compute on full series, keep points landing on/after visible window start.

    With 600 candles and limit=300, the first projected time must equal the
    first candle of candles[-300:] (warmup must not be discarded before compute).
    """
    candles = _make_candles(600)
    limit = 300
    params = IchimokuParams()
    window = candles[-limit:]
    window_start = window[0].time

    full = compute_projected_kumo(candles, params)
    filtered = [p for p in full if int(p["time_projected"]) >= window_start]

    assert filtered, "expected projected points for the visible window"
    assert int(filtered[0]["time_projected"]) == window_start

    # Contrast: computing only on the truncated window loses early cloud.
    truncated = compute_projected_kumo(window, params)
    assert int(truncated[0]["time_projected"]) > window_start
