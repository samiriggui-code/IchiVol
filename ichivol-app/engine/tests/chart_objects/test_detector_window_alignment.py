"""T2a fix — trendline bar indices are relative to each detector's window.

pytrendline caps at ``pytrendline_max_bars`` (default 150) while structure
``window_bars`` may be 300. Mapping ``start_bar``/``end_bar`` through the full
window shifts drawn lines ~150 bars too early.
"""

from __future__ import annotations

from app.api.common import _line_dict
from app.chart_objects.from_structure import structure_to_chart_objects
from app.chart_objects.types import ChartObjectType
from app.structure.params import StructureEngineParams
from app.structure.service import detect_market_structure
from app.structure.types import LevelSide
from tests.structure.test_structure_engines import _make_candles


def _detector_series(window, ms):
    bars = int(ms.meta.get("bars") or len(window))
    return list(window[-bars:]), bars


def test_trendline_bars_align_to_detector_window():
    candles = _make_candles(400, seed=7)
    params = StructureEngineParams(window_bars=300, pytrendline_max_bars=150)
    snap = detect_market_structure(candles, params, include_pytrendline=True)
    window = list(candles[-params.window_bars :])

    saw_lines = False
    for name, ms in snap.by_detector.items():
        series, bars = _detector_series(window, ms)
        assert ms.meta.get("bars") == bars
        lines = list(ms.support_trendlines) + list(ms.resistance_trendlines)
        if not lines:
            continue
        saw_lines = True
        pivots_by_bar = {(p.bar_index, p.side): p for p in ms.pivots}
        t0, t1 = series[0].time, series[-1].time
        for line in lines:
            for pb in line.pivot_bars:
                assert 0 <= pb < len(series), f"{name}: pivot_bar {pb} out of detector window"
                candle = series[pb]
                pivot = pivots_by_bar.get((pb, line.side))
                if pivot is not None:
                    assert pivot.time == candle.time
                    # Wick-based detectors: pivot price is candle low/high.
                    # MVPP may use body extremes on low-volume bars.
                    if name != "mvpp":
                        extreme = (
                            candle.low if line.side == LevelSide.SUPPORT else candle.high
                        )
                        assert abs(extreme - pivot.price) < 1e-9, (
                            f"{name}: pivot_bar {pb} price mismatch vs candle extreme"
                        )
                    else:
                        assert candle.low - 1e-9 <= pivot.price <= candle.high + 1e-9
            out = _line_dict(line, series)
            assert "start_time" in out and "end_time" in out
            assert t0 <= out["start_time"] <= t1
            assert t0 <= out["end_time"] <= t1
            assert out["start_time"] == series[line.start_bar].time
            assert out["end_time"] == series[line.end_bar].time

    assert saw_lines, "expected at least one detector with trendlines on seed 7"

    pyt = snap.by_detector["pytrendline"]
    assert pyt.meta["bars"] == 150
    assert pyt.support_trendlines, "pytrendline should emit support lines on seed 7"
    line = pyt.support_trendlines[0]
    det = window[-150:]
    correct = _line_dict(line, det)
    wrong = _line_dict(line, window)  # pre-fix: indices into full 300-bar window
    assert correct["start_time"] == det[line.start_bar].time
    assert correct["start_time"] != wrong["start_time"], (
        "pytrendline first support must not be offset by ~150 bars via full window"
    )
    assert correct["start_time"] == window[150 + line.start_bar].time

    objs = structure_to_chart_objects(snap, "BTCUSDT", "1h", window)
    pyt_lines = [
        o
        for o in objs
        if o.type == ChartObjectType.TREND_LINE
        and o.origin.get("detector") == "pytrendline"
        and o.side == "support"
    ]
    if pyt_lines:
        # Top-N may drop this line; when present it must use detector-window times.
        assert pyt_lines[0].points[0].time == correct["start_time"]


def test_structure_without_pytrendline_times_unchanged():
    """Golden path: include_pytrendline=False must match full-window _line_dict."""
    candles = _make_candles(400, seed=7)
    params = StructureEngineParams(window_bars=300)
    snap = detect_market_structure(candles, params, include_pytrendline=False)
    window = list(candles[-params.window_bars :])
    assert "pytrendline" not in snap.by_detector

    for name, ms in snap.by_detector.items():
        series, bars = _detector_series(window, ms)
        assert bars == len(window), f"{name} should use full window_bars without pytrendline cap"
        assert series == window
        for line in list(ms.support_trendlines) + list(ms.resistance_trendlines):
            assert _line_dict(line, series) == _line_dict(line, window)
