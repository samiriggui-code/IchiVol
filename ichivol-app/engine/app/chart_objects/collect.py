"""Collect ChartObjects from ENGINE (structure) + persisted overlays (T2b)."""

from __future__ import annotations

from typing import Any

from app.chart_objects.from_structure import structure_to_chart_objects
from app.chart_objects.store import list_chart_objects
from app.chart_objects.types import ChartObjectSource
from app.db.session import SessionLocal
from app.market_data import twelve_data
from app.market_data.resolve import resolve_and_fetch
from app.structure.params import StructureEngineParams
from app.structure.service import detect_market_structure


def parse_sources(sources: str | list[str] | None) -> list[str]:
    if sources is None:
        return [ChartObjectSource.ENGINE.value]
    if isinstance(sources, list):
        parts = [str(s).strip().lower() for s in sources if str(s).strip()]
    else:
        parts = [p.strip().lower() for p in str(sources).split(",") if p.strip()]
    out: list[str] = []
    for raw in parts:
        try:
            out.append(ChartObjectSource(raw).value)
        except ValueError as exc:
            raise ValueError(f"invalid_source: {raw!r}") from exc
    return out or [ChartObjectSource.ENGINE.value]


def collect_chart_objects(
    *,
    symbol: str,
    timeframe: str = "1h",
    limit: int = 300,
    sources: str | list[str] | None = "engine",
    include_pytrendline: bool = False,
    x_twelve_data_key: str | None = None,
) -> dict[str, Any]:
    """Merge ENGINE (live structure) + USER/CLAUDE (store) overlays."""
    requested = parse_sources(sources)
    objects: list[dict[str, Any]] = []
    provider: str | None = None
    provider_symbol: str | None = None
    as_of: int | None = None
    sym = symbol.upper()

    if ChartObjectSource.ENGINE.value in requested:
        twelve_data.set_api_key_override(x_twelve_data_key)
        prov, provider_symbol, candles = resolve_and_fetch(
            sym, timeframe, min(limit, 500)
        )
        provider = prov.id
        params = StructureEngineParams(window_bars=min(limit, 500))
        snap = detect_market_structure(
            candles, params, include_pytrendline=include_pytrendline
        )
        window = list(candles[-params.window_bars :])
        as_of = int(window[-1].time) if window else None
        objects.extend(
            o.to_dict()
            for o in structure_to_chart_objects(snap, sym, timeframe, window)
        )

    persist_sources = [
        s
        for s in requested
        if s in (ChartObjectSource.USER.value, ChartObjectSource.CLAUDE.value)
    ]
    if persist_sources:
        session = SessionLocal()
        try:
            stored = list_chart_objects(
                session, symbol=sym, timeframe=timeframe, sources=persist_sources
            )
            objects.extend(o.to_dict() for o in stored)
            if as_of is None and stored:
                as_of = max(o.as_of for o in stored)
        finally:
            session.close()

    return {
        "symbol": sym,
        "timeframe": timeframe,
        "provider": provider,
        "provider_symbol": provider_symbol,
        "as_of": as_of,
        "sources": requested,
        "objects": objects,
        "count": len(objects),
    }
