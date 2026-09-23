"""T1f — pivot confirmation causality / stability tests (measure & mark only)."""

from __future__ import annotations

import random

import pytest

from app.indicators.ichimoku import Candle
from app.structure.adapters import (
    MvppStructureAdapter,
    PyTrendlineStructureAdapter,
    TrendlnStructureAdapter,
)
from app.structure.consensus import build_consensus
from app.structure.params import StructureEngineParams
from app.structure.types import LevelSide, MarketStructure, PivotPoint


SEEDS = (7, 42)
CHECK_TS = (80, 120, 160, 200, 250)
STABILITY_KS = (1, 5, 20)


def _make_candles(n: int, seed: int) -> list[Candle]:
    rng = random.Random(seed)
    price = 100.0
    out: list[Candle] = []
    for i in range(n):
        drift = 0.15 + rng.uniform(-1.2, 1.2)
        o = price
        c = max(1.0, price + drift)
        h = max(o, c) + rng.uniform(0.1, 1.5)
        l = min(o, c) - rng.uniform(0.1, 1.5)
        v = rng.uniform(50, 500)
        if i % 17 == 0:
            v *= 3.0
        out.append(Candle(time=i, open=o, high=h, low=l, close=c, volume=v))
        price = c
    return out


def _params() -> StructureEngineParams:
    return StructureEngineParams(
        window_bars=300,
        pytrendline_max_bars=150,
        pytrendline_offline_only=False,
        min_detectors_agree=1,
    )


def _snapshot_mvpp(candles: list[Candle], params: StructureEngineParams) -> MarketStructure:
    return MvppStructureAdapter().detect(candles, params)


def _snapshot_trendln(candles: list[Candle], params: StructureEngineParams) -> MarketStructure:
    return TrendlnStructureAdapter().detect(candles, params)


def _snapshot_pytrendline(candles: list[Candle], params: StructureEngineParams) -> MarketStructure:
    return PyTrendlineStructureAdapter().detect(candles, params, allow_online=True)


def _snapshot_consensus(candles: list[Candle], params: StructureEngineParams) -> MarketStructure:
    # Default production consensus (detect_market_structure): mvpp + trendln.
    # Both share window_bars=300 so bar_index stays aligned without pytrendline's 150-bar slide.
    parts = [
        _snapshot_mvpp(candles, params),
        _snapshot_trendln(candles, params),
    ]
    return build_consensus(parts, params, atr=None)


ADAPTERS = {
    "mvpp": (_snapshot_mvpp, 300),
    "trendln": (_snapshot_trendln, 300),
    # pytrendline windows via pytrendline_max_bars (150); common-window remap below.
    "pytrendline": (_snapshot_pytrendline, 150),
    "consensus": (_snapshot_consensus, 300),
}


def _window_offset(n_input: int, max_bars: int) -> int:
    return max(0, n_input - max_bars)


def _abs_key(p: PivotPoint, offset: int) -> tuple[int, float, LevelSide]:
    return (p.bar_index + offset, p.price, p.side)


@pytest.mark.parametrize("adapter_name", list(ADAPTERS))
@pytest.mark.parametrize("seed", SEEDS)
def test_confirmed_bar_known_by_snapshot_end(adapter_name: str, seed: int):
    """(a) Every pivot in snapshot(candles[:t]) has confirmed_bar <= t-1."""
    candles = _make_candles(300, seed)
    params = _params()
    snap_fn, _max_bars = ADAPTERS[adapter_name]
    for t in CHECK_TS:
        snap = snap_fn(candles[:t], params)
        for p in snap.pivots:
            assert p.confirmed_bar is not None, f"{adapter_name} pivot missing confirmed_bar"
            assert p.confirmed_bar <= t - 1, (
                f"{adapter_name} seed={seed} t={t}: confirmed_bar={p.confirmed_bar} > t-1={t - 1}"
            )


@pytest.mark.parametrize("adapter_name", list(ADAPTERS))
@pytest.mark.parametrize("seed", SEEDS)
def test_non_provisional_pivots_are_stable(adapter_name: str, seed: int):
    """(b) Non-provisional pivots persist identically for k in {1,5,20}.

    When an adapter windows bars (max_bars), identity is compared in the
    common absolute window via bar_index + offset. Pivots within ``lookback``
    of the left edge of the later window are excluded: sliding the series
    drops left context for fractal confirmation (documented for pytrendline,
    lookback=3). This is a windowing artefact, distinct from provisional anchors.
    """
    candles = _make_candles(300, seed)
    params = _params()
    snap_fn, max_bars = ADAPTERS[adapter_name]
    # Fractal / extrema left-context required inside the windowed series.
    left_ctx = {
        "mvpp": params.fractal_left,
        "trendln": params.extrema_lookback,
        "pytrendline": 3,  # _pivots(..., lookback=3)
        "consensus": 0,  # mvpp+trendln only; no slide for t<=250 with window_bars=300
    }[adapter_name]
    for t in CHECK_TS:
        if t + max(STABILITY_KS) > len(candles):
            continue
        snap_t = snap_fn(candles[:t], params)
        off_t = _window_offset(t, max_bars)
        win_lo_t = off_t
        win_hi_t = t - 1
        stable = [p for p in snap_t.pivots if not p.provisional]
        for k in STABILITY_KS:
            snap_k = snap_fn(candles[: t + k], params)
            off_k = _window_offset(t + k, max_bars)
            win_lo_k = off_k
            win_hi_k = t + k - 1
            # Common absolute bars present in both detector windows.
            common_lo = max(win_lo_t, win_lo_k)
            common_hi = min(win_hi_t, win_hi_k)
            later = {_abs_key(p, off_k) for p in snap_k.pivots}
            for p in stable:
                abs_i = p.bar_index + off_t
                if abs_i < common_lo or abs_i > common_hi:
                    continue
                # Need full left lookback inside the later windowed series.
                if abs_i < common_lo + left_ctx:
                    continue
                key = _abs_key(p, off_t)
                assert key in later, (
                    f"{adapter_name} seed={seed} t={t} k={k}: "
                    f"non-provisional pivot {key} missing after +{k} bars "
                    f"(common_window=[{common_lo},{common_hi}], left_ctx={left_ctx})"
                )


@pytest.mark.parametrize("seed", SEEDS)
def test_pytrendline_provisional_anchors_repaint(seed: int):
    """(c) Documents current pytrendline repaint: a provisional anchor at t vanishes at t+1."""
    candles = _make_candles(300, seed)
    params = _params()
    found = False
    for t in CHECK_TS:
        if t + 1 > len(candles):
            continue
        snap_t = _snapshot_pytrendline(candles[:t], params)
        snap_next = _snapshot_pytrendline(candles[: t + 1], params)
        off_t = _window_offset(t, params.pytrendline_max_bars)
        off_n = _window_offset(t + 1, params.pytrendline_max_bars)
        later = {_abs_key(p, off_n) for p in snap_next.pivots}
        for p in snap_t.pivots:
            if not p.provisional:
                continue
            key = _abs_key(p, off_t)
            if key not in later:
                found = True
                break
        if found:
            break
    assert found, (
        "expected at least one provisional pytrendline anchor to disappear "
        f"between t and t+1 (seed={seed}); behaviour under test is current repaint"
    )
