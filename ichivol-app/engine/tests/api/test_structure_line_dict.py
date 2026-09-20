from __future__ import annotations

from app.api.routes import _line_dict
from app.indicators.ichimoku import Candle
from app.structure.types import DetectorSource, LevelSide, TrendlineSegment


def _line(start: int, end: int) -> TrendlineSegment:
    return TrendlineSegment(
        side=LevelSide.SUPPORT,
        slope=2.0,
        intercept=100.0,
        start_bar=start,
        end_bar=end,
        touch_count=3,
        score=0.7,
        source=DetectorSource.MVPP,
    )


def _series(n: int) -> list[Candle]:
    return [Candle(time=1_000 + i * 60, open=1, high=1, low=1, close=1) for i in range(n)]


def test_line_dict_adds_absolute_time_and_price_from_the_windowed_series():
    out = _line_dict(_line(2, 7), _series(10))
    assert out["start_time"] == 1_120
    assert out["end_time"] == 1_420
    assert out["start_price"] == 104.0
    assert out["end_price"] == 114.0


def test_line_dict_without_series_keeps_the_legacy_shape():
    out = _line_dict(_line(2, 7))
    assert "start_time" not in out
    assert out["start_bar"] == 2


def test_line_dict_skips_time_fields_when_indices_fall_outside_the_series():
    out = _line_dict(_line(2, 50), _series(10))
    assert "start_time" not in out
