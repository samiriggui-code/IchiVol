"""Produce confluence *zones* from overlapping ChartObjects (layer=confluence).

Score is honest ``score_is_mock=True`` until a validated confluence scorer exists.
Families come from object layers already produced (structure / fib / fvg / liquidity).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

from app.chart_objects.types import (
    ChartObject,
    ChartObjectLayer,
    ChartObjectSource,
    ChartObjectType,
    ChartPoint,
    round_chart_coord,
)
from app.indicators.ichimoku import Candle
from app.structure.atr_utils import last_atr, touch_tolerance


@dataclass(frozen=True)
class ConfluenceParams:
    atr_period: int = 14
    band_atr_mult: float = 0.35
    min_families: int = 2
    max_zones: int = 4


_FAMILY_BY_LAYER = {
    "structure": "structure",
    "breaks": "structure",
    "fibonacci": "location",
    "fvg": "structure",
    "liquidity": "structure",
}


@dataclass
class _Level:
    price: float
    family: str
    label: str
    value: str
    known_at: int
    layer: str


def _levels_from_objects(objects: Sequence[ChartObject | dict[str, Any]]) -> list[_Level]:
    out: list[_Level] = []
    for raw in objects:
        o = raw.to_dict() if isinstance(raw, ChartObject) else dict(raw)
        layer = str(o.get("layer") or "")
        if layer in ("confluence", "ichimoku", "claude", "user_trades", "backtest"):
            continue
        family = _FAMILY_BY_LAYER.get(layer)
        if family is None:
            continue
        origin = dict(o.get("origin") or {})
        known = origin.get("known_at")
        if known is None and o.get("points"):
            known = o["points"][0].get("time") if isinstance(o["points"][0], dict) else None
        if known is None:
            known = o.get("as_of") or 0
        known_at = int(known)

        label = str(o.get("label") or origin.get("kind") or layer)
        prices: list[float] = []
        if o.get("price_low") is not None and o.get("price_high") is not None:
            lo = float(o["price_low"])
            hi = float(o["price_high"])
            prices.append((lo + hi) / 2.0)
        for pt in o.get("points") or []:
            if isinstance(pt, dict) and pt.get("price") is not None:
                prices.append(float(pt["price"]))
            elif hasattr(pt, "price"):
                prices.append(float(pt.price))
        # Fib: one object per level — use first point.
        if origin.get("kind") == "fibonacci" and prices:
            prices = [prices[0]]

        for px in prices:
            out.append(
                _Level(
                    price=float(px),
                    family=family,
                    label=label[:48],
                    value=str(round_chart_coord(px)),
                    known_at=known_at,
                    layer=layer,
                )
            )
    return out


def _cluster_levels(levels: list[_Level], *, tol: float) -> list[list[_Level]]:
    if not levels:
        return []
    ordered = sorted(levels, key=lambda x: x.price)
    clusters: list[list[_Level]] = []
    cur = [ordered[0]]
    for lv in ordered[1:]:
        ref = sum(x.price for x in cur) / len(cur)
        if abs(lv.price - ref) <= tol:
            cur.append(lv)
        else:
            clusters.append(cur)
            cur = [lv]
    clusters.append(cur)
    return clusters


def confluence_to_chart_objects(
    candles: Sequence[Candle],
    symbol: str,
    timeframe: str,
    objects: Sequence[ChartObject | dict[str, Any]],
    *,
    params: ConfluenceParams | None = None,
) -> list[ChartObject]:
    """Emit zones where ≥2 producer families overlap within an ATR band."""
    if not candles or not objects:
        return []
    p = params or ConfluenceParams()
    atr = last_atr(candles, p.atr_period)
    mid = float(candles[-1].close)
    tol = touch_tolerance(atr, p.band_atr_mult, mid)
    if tol <= 0:
        return []

    levels = _levels_from_objects(objects)
    as_of = int(candles[-1].time)
    sym = symbol.upper()
    zones: list[ChartObject] = []

    for cluster in _cluster_levels(levels, tol=tol):
        families = {x.family for x in cluster}
        layers = {x.layer for x in cluster}
        if len(families) < p.min_families and len(layers) < p.min_families:
            continue
        # Distinct layers preferred (fib+fvg+structure).
        if len(layers) < p.min_families:
            continue
        prices = [x.price for x in cluster]
        lo = min(prices) - tol * 0.25
        hi = max(prices) + tol * 0.25
        if not (lo < hi):
            continue
        known_at = max(x.known_at for x in cluster)
        # Dedupe component labels.
        comps: list[dict[str, Any]] = []
        seen: set[str] = set()
        for x in sorted(cluster, key=lambda z: z.layer):
            key = f"{x.layer}:{x.label}:{x.value}"
            if key in seen:
                continue
            seen.add(key)
            comps.append(
                {
                    "family": x.family,
                    "label": x.label,
                    "value": x.value,
                    "satisfied": True,
                }
            )
        pl = round_chart_coord(lo)
        ph = round_chart_coord(hi)
        lineage_key = f"confluence:{pl}:{ph}:{known_at}"
        n_layers = len(layers)
        conf = min(0.95, 0.5 + 0.12 * (n_layers - 2))
        t0 = max(0, known_at)
        zones.append(
            ChartObject(
                type=ChartObjectType.ZONE,
                source=ChartObjectSource.ENGINE,
                layer=ChartObjectLayer.CONFLUENCE,
                symbol=sym,
                timeframe=timeframe,
                points=(
                    ChartPoint(time=t0, price=(lo + hi) / 2.0),
                    ChartPoint(time=as_of, price=(lo + hi) / 2.0),
                ),
                price_low=float(lo),
                price_high=float(hi),
                as_of=as_of,
                side="support" if mid >= (lo + hi) / 2 else "resistance",
                label="CONFLUENCE",
                confidence=conf,
                subtype="overlap",
                origin={
                    "kind": "confluence",
                    "producer": "confluence_engine",
                    "status": "open",
                    "known_at": known_at,
                    "score_is_mock": True,
                    "lineage_key": lineage_key,
                    "reason": (
                        f"{n_layers} calques convergent dans [{pl}, {ph}] "
                        "(score prototype — non validé VP)."
                    ),
                    "used_by_decision": False,
                    "components": comps[:8],
                },
            )
        )

    zones.sort(key=lambda z: len((z.origin or {}).get("components") or []), reverse=True)
    return zones[: p.max_zones]
