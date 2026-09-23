"""T1f / T1f-2 — pivot confirmation causality and pytrendline no-repaint."""

from __future__ import annotations

import json
import random
from pathlib import Path

import pytest

from app.indicators.ichimoku import Candle
from app.structure.adapters import (
    MvppStructureAdapter,
    PyTrendlineStructureAdapter,
    TrendlnStructureAdapter,
)
from app.structure.consensus import build_consensus
from app.structure.params import StructureEngineParams
from app.structure.types import LevelSide, MarketStructure, PivotPoint, TrendlineSegment


SEEDS = (7, 42)
CHECK_TS = (80, 120, 160, 200, 250)
STABILITY_KS = (1, 5, 20)
_GOLDEN = Path(__file__).resolve().parent / "fixtures" / "pytrendline_provisional_anchors_golden.json"


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


def _params(**overrides) -> StructureEngineParams:
    base = dict(
        window_bars=300,
        pytrendline_max_bars=150,
        pytrendline_offline_only=False,
        min_detectors_agree=1,
        allow_provisional_anchors=False,
    )
    base.update(overrides)
    return StructureEngineParams(**base)


def _snapshot_mvpp(candles: list[Candle], params: StructureEngineParams) -> MarketStructure:
    return MvppStructureAdapter().detect(candles, params)


def _snapshot_trendln(candles: list[Candle], params: StructureEngineParams) -> MarketStructure:
    return TrendlnStructureAdapter().detect(candles, params)


def _snapshot_pytrendline(candles: list[Candle], params: StructureEngineParams) -> MarketStructure:
    return PyTrendlineStructureAdapter().detect(candles, params, allow_online=True)


def _snapshot_consensus(candles: list[Candle], params: StructureEngineParams) -> MarketStructure:
    # Default production consensus (detect_market_structure): mvpp + trendln.
    parts = [
        _snapshot_mvpp(candles, params),
        _snapshot_trendln(candles, params),
    ]
    return build_consensus(parts, params, atr=None)


ADAPTERS = {
    "mvpp": (_snapshot_mvpp, 300),
    "trendln": (_snapshot_trendln, 300),
    "pytrendline": (_snapshot_pytrendline, 150),
    "consensus": (_snapshot_consensus, 300),
}


def _window_offset(n_input: int, max_bars: int) -> int:
    return max(0, n_input - max_bars)


def _abs_key(p: PivotPoint, offset: int) -> tuple[int, float, LevelSide]:
    return (p.bar_index + offset, p.price, p.side)


def _lines(ms: MarketStructure) -> list[TrendlineSegment]:
    return list(ms.support_trendlines) + list(ms.resistance_trendlines)


def _line_fit_from_confirmed(line: TrendlineSegment, pivots: tuple[PivotPoint, ...]) -> bool:
    """True iff some pair of non-provisional same-side pivots reproduces the line."""
    confirmed = [p for p in pivots if not p.provisional and p.side == line.side]
    for i, p0 in enumerate(confirmed):
        for p1 in confirmed[i + 1 :]:
            if p1.bar_index == p0.bar_index:
                continue
            slope = (p1.price - p0.price) / (p1.bar_index - p0.bar_index)
            intercept = p0.price - slope * p0.bar_index
            if abs(slope - line.slope) < 1e-12 and abs(intercept - line.intercept) < 1e-9:
                return True
    return False


def _abs_line_id(line: TrendlineSegment, offset: int) -> tuple:
    """Identity for stability: side + slope + absolute touch bars."""
    return (
        line.side.value,
        round(line.slope, 12),
        tuple(sorted(b + offset for b in line.pivot_bars)),
    )


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
    left_ctx = {
        "mvpp": params.fractal_left,
        "trendln": params.extrema_lookback,
        "pytrendline": 3,
        "consensus": 0,
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
            common_lo = max(win_lo_t, win_lo_k)
            common_hi = min(win_hi_t, win_hi_k)
            later = {_abs_key(p, off_k) for p in snap_k.pivots}
            for p in stable:
                abs_i = p.bar_index + off_t
                if abs_i < common_lo or abs_i > common_hi:
                    continue
                if abs_i < common_lo + left_ctx:
                    continue
                key = _abs_key(p, off_t)
                assert key in later, (
                    f"{adapter_name} seed={seed} t={t} k={k}: "
                    f"non-provisional pivot {key} missing after +{k} bars "
                    f"(common_window=[{common_lo},{common_hi}], left_ctx={left_ctx})"
                )


@pytest.mark.parametrize("seed", SEEDS)
def test_pytrendline_trendlines_use_only_confirmed_pivots(seed: int):
    """(c) Default: every pytrendline trendline is fit from non-provisional pivots only."""
    candles = _make_candles(300, seed)
    params = _params(allow_provisional_anchors=False)
    for t in CHECK_TS:
        snap = _snapshot_pytrendline(candles[:t], params)
        for line in _lines(snap):
            assert _line_fit_from_confirmed(line, snap.pivots), (
                f"seed={seed} t={t}: line slope={line.slope} not reproducible "
                f"from confirmed pivots alone (provisional anchors must not fit)"
            )


@pytest.mark.parametrize("seed", SEEDS)
def test_pytrendline_trendline_stability_no_mutation(seed: int):
    """Line present at t whose fit pivots remain in window at t+1 is identical or gone — never mutated.

    Identity = (side, absolute fit_pivot_bars). Same fit pair ⇒ same slope; a different
    slope with the same fit pair is impossible unless prices changed (forbidden for
    confirmed fractals). Disappearance is allowed (breakout / invalidation / top-N drop).
    """
    candles = _make_candles(300, seed)
    params = _params(allow_provisional_anchors=False)
    max_bars = params.pytrendline_max_bars
    for t in CHECK_TS:
        if t + 1 > len(candles):
            continue
        snap_t = _snapshot_pytrendline(candles[:t], params)
        snap_n = _snapshot_pytrendline(candles[: t + 1], params)
        off_t = _window_offset(t, max_bars)
        off_n = _window_offset(t + 1, max_bars)
        win_lo_n = off_n
        win_hi_n = t
        later_by_fit: dict[tuple, list[TrendlineSegment]] = {}
        for ln in _lines(snap_n):
            if len(ln.fit_pivot_bars) < 2:
                continue
            key = (ln.side.value, tuple(sorted(b + off_n for b in ln.fit_pivot_bars)))
            later_by_fit.setdefault(key, []).append(ln)

        for ln in _lines(snap_t):
            if len(ln.fit_pivot_bars) < 2:
                continue
            abs_fit = tuple(sorted(b + off_t for b in ln.fit_pivot_bars))
            if abs_fit[0] < win_lo_n or abs_fit[-1] > win_hi_n:
                continue
            key = (ln.side.value, abs_fit)
            matches = later_by_fit.get(key, [])
            if not matches:
                # Disappeared: breakout / invalidation / ranking — documented OK.
                continue
            for m in matches:
                assert abs(m.slope - ln.slope) < 1e-12, (
                    f"seed={seed} t={t}: trendline mutated slope "
                    f"{ln.slope} -> {m.slope} for fit_pivots {abs_fit}"
                )
                # Intercept is window-relative; only comparable when offsets match.
                if off_t == off_n:
                    assert abs(m.intercept - ln.intercept) < 1e-9


@pytest.mark.parametrize("seed", SEEDS)
def test_allow_provisional_anchors_matches_legacy_golden(seed: int):
    """allow_provisional_anchors=True reproduces pre-T1f-2 pytrendline fixtures."""
    candles = _make_candles(300, seed)
    params = _params(allow_provisional_anchors=True)
    ms = _snapshot_pytrendline(candles, params)
    golden = json.loads(_GOLDEN.read_text())[f"seed_{seed}"]

    def line_dict(ln: TrendlineSegment) -> dict:
        return {
            "side": ln.side.value,
            "slope": ln.slope,
            "intercept": ln.intercept,
            "start_bar": ln.start_bar,
            "end_bar": ln.end_bar,
            "touch_count": ln.touch_count,
            "score": ln.score,
            "pivot_bars": list(ln.pivot_bars),
        }

    def zone_dict(z) -> dict:
        return {
            "side": z.side.value,
            "low": z.low,
            "high": z.high,
            "mid": z.mid,
            "score": z.score,
            "touch_count": z.touch_count,
        }

    actual = {
        "structure_score": ms.structure_score,
        "n_pivots": len(ms.pivots),
        "n_provisional_pivots": sum(1 for p in ms.pivots if p.provisional),
        "support_trendlines": [line_dict(x) for x in ms.support_trendlines],
        "resistance_trendlines": [line_dict(x) for x in ms.resistance_trendlines],
        "support_zones": [zone_dict(x) for x in ms.support_zones],
        "resistance_zones": [zone_dict(x) for x in ms.resistance_zones],
        "meta_bars": ms.meta.get("bars"),
    }
    assert actual == golden
