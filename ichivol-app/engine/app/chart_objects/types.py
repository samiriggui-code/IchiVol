"""Canonical ChartObject model for IchiVol drawable overlays (T2a).

Immutable, serializable, deterministic-id objects produced by the engine
(and later USER / Claude / strategy / backtest). Validation is type-specific;
invalid combinations raise ``ValueError``.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ChartObjectType(str, Enum):
    HORIZONTAL_LINE = "horizontal_line"
    TREND_LINE = "trend_line"
    RAY = "ray"
    ZONE = "zone"
    RECTANGLE = "rectangle"
    CHANNEL = "channel"
    MARKER = "marker"
    TEXT = "text"
    ENTRY = "entry"
    STOP = "stop"
    TARGET = "target"


class ChartObjectSource(str, Enum):
    USER = "user"
    ENGINE = "engine"
    CLAUDE = "claude"
    STRATEGY = "strategy"
    BACKTEST = "backtest"


@dataclass(frozen=True)
class ChartPoint:
    time: int
    price: float


def _round_coord(value: float, ndigits: int = 8) -> float:
    return round(float(value), ndigits)


def _id_payload(
    *,
    type: ChartObjectType,
    source: ChartObjectSource,
    symbol: str,
    timeframe: str,
    points: tuple[ChartPoint, ...],
    price_low: float | None,
    price_high: float | None,
    subtype: str | None,
) -> str:
    """Stable fingerprint inputs (rounded coords) for deterministic ids."""
    body = {
        "type": type.value,
        "source": source.value,
        "symbol": symbol.upper(),
        "timeframe": timeframe,
        "subtype": subtype or "",
        "price_low": None if price_low is None else _round_coord(price_low),
        "price_high": None if price_high is None else _round_coord(price_high),
        "points": [
            {"time": int(p.time), "price": _round_coord(p.price)} for p in points
        ],
    }
    return json.dumps(body, sort_keys=True, separators=(",", ":"))


def deterministic_chart_object_id(
    *,
    type: ChartObjectType,
    source: ChartObjectSource,
    symbol: str,
    timeframe: str,
    points: tuple[ChartPoint, ...],
    price_low: float | None = None,
    price_high: float | None = None,
    subtype: str | None = None,
) -> str:
    digest = hashlib.sha256(
        _id_payload(
            type=type,
            source=source,
            symbol=symbol,
            timeframe=timeframe,
            points=points,
            price_low=price_low,
            price_high=price_high,
            subtype=subtype,
        ).encode("utf-8")
    ).hexdigest()
    return digest[:24]


def _validate(obj: ChartObject) -> None:
    if not (0.0 <= obj.confidence <= 1.0):
        raise ValueError(f"confidence must be in [0, 1], got {obj.confidence}")
    if not obj.symbol:
        raise ValueError("symbol is required")
    if not obj.timeframe:
        raise ValueError("timeframe is required")
    if obj.as_of < 0:
        raise ValueError("as_of must be >= 0")

    t = obj.type
    n = len(obj.points)

    if t == ChartObjectType.HORIZONTAL_LINE:
        if n != 1:
            raise ValueError("HORIZONTAL_LINE requires exactly 1 point")
    elif t == ChartObjectType.TREND_LINE:
        if n != 2:
            raise ValueError("TREND_LINE requires exactly 2 points")
        if obj.points[1].time <= obj.points[0].time:
            raise ValueError("TREND_LINE end time must be > start time")
    elif t == ChartObjectType.RAY:
        if n != 2:
            raise ValueError("RAY requires exactly 2 points")
        if obj.points[1].time <= obj.points[0].time:
            raise ValueError("RAY end time must be > start time")
    elif t == ChartObjectType.ZONE:
        if obj.price_low is None or obj.price_high is None:
            raise ValueError("ZONE requires price_low and price_high")
        if not (obj.price_low < obj.price_high):
            raise ValueError("ZONE requires price_low < price_high")
        if n not in (0, 2):
            raise ValueError("ZONE points must be empty or exactly 2")
    elif t == ChartObjectType.RECTANGLE:
        if n != 2:
            raise ValueError("RECTANGLE requires exactly 2 points")
        if obj.points[1].time <= obj.points[0].time:
            raise ValueError("RECTANGLE end time must be > start time")
        if obj.price_low is None or obj.price_high is None:
            raise ValueError("RECTANGLE requires price_low and price_high")
        if not (obj.price_low < obj.price_high):
            raise ValueError("RECTANGLE requires price_low < price_high")
    elif t == ChartObjectType.CHANNEL:
        if n != 4:
            raise ValueError("CHANNEL requires exactly 4 points (two segments)")
    elif t == ChartObjectType.MARKER:
        if n != 1:
            raise ValueError("MARKER requires exactly 1 point")
    elif t == ChartObjectType.TEXT:
        if n != 1:
            raise ValueError("TEXT requires exactly 1 point")
        if not (obj.label and obj.label.strip()):
            raise ValueError("TEXT requires a non-empty label")
    elif t in (ChartObjectType.ENTRY, ChartObjectType.STOP, ChartObjectType.TARGET):
        if n != 1:
            raise ValueError(f"{t.name} requires exactly 1 point")
    else:
        raise ValueError(f"unsupported ChartObjectType: {t}")

    projected = bool(obj.origin.get("projected"))
    for p in obj.points:
        if p.time > obj.as_of and not projected:
            raise ValueError(
                f"point time {p.time} > as_of {obj.as_of} "
                "(set origin.projected=True for extensions)"
            )


@dataclass(frozen=True)
class ChartObject:
    """Drawable chart primitive with a deterministic id.

    ``id`` is a hash of (type, source, symbol, timeframe, rounded coordinates,
    subtype). Callers may pass ``id=None`` to compute it; an explicit id that
    disagrees with the fingerprint raises ``ValueError``.
    """

    type: ChartObjectType
    source: ChartObjectSource
    symbol: str
    timeframe: str
    points: tuple[ChartPoint, ...]
    as_of: int
    id: str = ""
    price_low: float | None = None
    price_high: float | None = None
    side: str | None = None
    label: str | None = None
    confidence: float = 0.0
    origin: dict[str, Any] = field(default_factory=dict)
    subtype: str | None = None

    def __post_init__(self) -> None:
        expected = deterministic_chart_object_id(
            type=self.type,
            source=self.source,
            symbol=self.symbol,
            timeframe=self.timeframe,
            points=self.points,
            price_low=self.price_low,
            price_high=self.price_high,
            subtype=self.subtype,
        )
        if not self.id:
            object.__setattr__(self, "id", expected)
        elif self.id != expected:
            raise ValueError(
                f"id mismatch: got {self.id!r}, expected {expected!r} "
                "from (type, source, symbol, timeframe, coords, subtype)"
            )
        # Normalize symbol casing for stable serialization.
        object.__setattr__(self, "symbol", self.symbol.upper())
        _validate(self)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type.value,
            "source": self.source.value,
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "points": [{"time": p.time, "price": p.price} for p in self.points],
            "price_low": self.price_low,
            "price_high": self.price_high,
            "side": self.side,
            "label": self.label,
            "confidence": self.confidence,
            "as_of": self.as_of,
            "origin": dict(self.origin),
            "subtype": self.subtype,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ChartObject:
        points_raw = data.get("points") or []
        points = tuple(
            ChartPoint(time=int(p["time"]), price=float(p["price"])) for p in points_raw
        )
        return cls(
            id=str(data.get("id") or ""),
            type=ChartObjectType(data["type"]),
            source=ChartObjectSource(data["source"]),
            symbol=str(data["symbol"]),
            timeframe=str(data["timeframe"]),
            points=points,
            price_low=None if data.get("price_low") is None else float(data["price_low"]),
            price_high=None if data.get("price_high") is None else float(data["price_high"]),
            side=data.get("side"),
            label=data.get("label"),
            confidence=float(data.get("confidence", 0.0)),
            as_of=int(data["as_of"]),
            origin=dict(data.get("origin") or {}),
            subtype=data.get("subtype"),
        )
