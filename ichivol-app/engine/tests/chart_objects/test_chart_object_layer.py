"""UI-MARKET — ChartObject.layer additive, id fingerprint unchanged."""

from __future__ import annotations

from app.chart_objects.types import (
    ChartObject,
    ChartObjectLayer,
    ChartObjectSource,
    ChartObjectType,
    ChartPoint,
    layer_from_source,
)


def _kw(**overrides):
    base = dict(
        type=ChartObjectType.MARKER,
        source=ChartObjectSource.ENGINE,
        symbol="BTCUSDT",
        timeframe="1h",
        points=(ChartPoint(time=100, price=42.5),),
        as_of=100,
        confidence=0.5,
        origin={"kind": "test"},
    )
    base.update(overrides)
    return base


def test_layer_defaults_from_source_and_stays_out_of_id():
    a = ChartObject(**_kw())
    b = ChartObject(**_kw(layer=ChartObjectLayer.STRUCTURE))
    assert a.layer == ChartObjectLayer.STRUCTURE
    assert a.id == b.id
    assert a.to_dict()["layer"] == "structure"


def test_from_dict_without_layer_deduces_source():
    payload = ChartObject(**_kw(source=ChartObjectSource.USER)).to_dict()
    del payload["layer"]
    restored = ChartObject.from_dict(payload)
    assert restored.layer == ChartObjectLayer.USER_TRADES
    assert layer_from_source(ChartObjectSource.BACKTEST) == ChartObjectLayer.BACKTEST
    assert layer_from_source(ChartObjectSource.CLAUDE) == ChartObjectLayer.CLAUDE
