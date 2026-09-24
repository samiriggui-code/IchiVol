"""Build ChartObject instances from agent draw_* args (T2b)."""

from __future__ import annotations

from typing import Any

from app.chart_objects.types import (
    ChartObject,
    ChartObjectLayer,
    ChartObjectSource,
    ChartObjectType,
    ChartPoint,
)


def _require_points(raw: Any, n: int | None = None) -> tuple[ChartPoint, ...]:
    if not isinstance(raw, list) or not raw:
        raise ValueError("points must be a non-empty list of {time, price}")
    points: list[ChartPoint] = []
    for i, p in enumerate(raw):
        if not isinstance(p, dict) or "time" not in p or "price" not in p:
            raise ValueError(f"points[{i}] must be {{time, price}}")
        points.append(ChartPoint(time=int(p["time"]), price=float(p["price"])))
    if n is not None and len(points) != n:
        raise ValueError(f"expected exactly {n} points, got {len(points)}")
    return tuple(points)


def _parse_source(raw: Any, *, agent_forced_claude: bool = False) -> ChartObjectSource:
    """Resolve persistable source.

    Agent draw_* always persists as CLAUDE (``agent_forced_claude=True``).
    USER is reserved for a future UI write path — not impersonable via agent.
    """
    if agent_forced_claude:
        if raw not in (None, "", "claude", ChartObjectSource.CLAUDE):
            raise ValueError(
                "agent draw_* always uses source=claude "
                "(USER overlays require a dedicated UI path)"
            )
        return ChartObjectSource.CLAUDE
    if raw is None or raw == "":
        return ChartObjectSource.CLAUDE
    try:
        src = ChartObjectSource(str(raw).strip().lower())
    except ValueError as exc:
        raise ValueError(f"invalid source: {raw!r}") from exc
    if src not in (ChartObjectSource.USER, ChartObjectSource.CLAUDE):
        raise ValueError("draw_* may only persist source=user|claude")
    return src


def _as_of_from_args(args: dict, points: tuple[ChartPoint, ...]) -> int:
    if args.get("as_of") is not None:
        return int(args["as_of"])
    if points:
        return max(p.time for p in points)
    raise ValueError("as_of is required when points are empty")


def build_from_draw_args(
    obj_type: ChartObjectType,
    args: dict,
    *,
    agent_channel: bool = True,
) -> ChartObject:
    """Validate agent args and return a ChartObject ready to persist.

    When ``agent_channel=True`` (default), source is forced to CLAUDE.
    """
    symbol = str(args.get("symbol") or "").strip().upper()
    timeframe = str(args.get("timeframe") or "1h").strip()
    if not symbol:
        raise ValueError("symbol is required")
    if not timeframe:
        raise ValueError("timeframe is required")

    source = _parse_source(args.get("source"), agent_forced_claude=agent_channel)
    label = args.get("label")
    side = args.get("side")
    subtype = args.get("subtype")
    confidence = float(args.get("confidence", 0.0))
    origin = dict(args.get("origin") or {})
    origin.setdefault("via", "agent_draw")

    price_low = None if args.get("price_low") is None else float(args["price_low"])
    price_high = None if args.get("price_high") is None else float(args["price_high"])

    if obj_type == ChartObjectType.HORIZONTAL_LINE:
        if args.get("price") is not None and not args.get("points"):
            t = int(args.get("time") or args.get("as_of") or 0)
            if t <= 0:
                raise ValueError("time or as_of required with price for horizontal_line")
            points = (ChartPoint(time=t, price=float(args["price"])),)
        else:
            points = _require_points(args.get("points"), 1)
    elif obj_type in (
        ChartObjectType.TREND_LINE,
        ChartObjectType.RAY,
        ChartObjectType.RECTANGLE,
    ):
        points = _require_points(args.get("points"), 2)
    elif obj_type == ChartObjectType.CHANNEL:
        points = _require_points(args.get("points"), 4)
    elif obj_type == ChartObjectType.ZONE:
        raw_pts = args.get("points")
        if raw_pts:
            points = _require_points(raw_pts)
            if len(points) not in (0, 2):
                raise ValueError("ZONE points must be empty or exactly 2")
        else:
            points = ()
        if price_low is None or price_high is None:
            raise ValueError("ZONE requires price_low and price_high")
    elif obj_type in (
        ChartObjectType.MARKER,
        ChartObjectType.TEXT,
        ChartObjectType.ENTRY,
        ChartObjectType.STOP,
        ChartObjectType.TARGET,
    ):
        if args.get("price") is not None and not args.get("points"):
            t = int(args.get("time") or args.get("as_of") or 0)
            if t <= 0:
                raise ValueError(f"time or as_of required with price for {obj_type.value}")
            points = (ChartPoint(time=t, price=float(args["price"])),)
        else:
            points = _require_points(args.get("points"), 1)
        if obj_type == ChartObjectType.TEXT and not (label and str(label).strip()):
            raise ValueError("TEXT requires a non-empty label")
    else:
        raise ValueError(f"unsupported draw type: {obj_type}")

    as_of = _as_of_from_args(args, points)
    if args.get("projected"):
        origin["projected"] = True

    return ChartObject(
        type=obj_type,
        source=source,
        layer=(
            ChartObjectLayer.USER_TRADES
            if source == ChartObjectSource.USER
            else ChartObjectLayer.CLAUDE
        ),
        symbol=symbol,
        timeframe=timeframe,
        points=points,
        as_of=as_of,
        price_low=price_low,
        price_high=price_high,
        side=None if side is None else str(side),
        label=None if label is None else str(label),
        confidence=confidence,
        origin=origin,
        subtype=None if subtype is None else str(subtype),
    )
