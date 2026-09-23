"""Serialize Market Structure snapshots for HTTP + agent channel (shared)."""

from __future__ import annotations

from typing import Any

from app.api.common import _line_dict, _zone_dict
from app.market_data import twelve_data
from app.market_data.resolve import resolve_and_fetch
from app.structure.params import StructureEngineParams
from app.structure.service import detect_market_structure


def build_structure_payload(
    *,
    symbol: str,
    timeframe: str = "1h",
    limit: int = 300,
    include_pytrendline: bool = False,
    x_twelve_data_key: str | None = None,
) -> dict[str, Any]:
    twelve_data.set_api_key_override(x_twelve_data_key)
    provider, provider_symbol, candles = resolve_and_fetch(
        symbol.upper(), timeframe, min(limit, 500)
    )
    params = StructureEngineParams(window_bars=min(limit, 500))
    snap = detect_market_structure(
        candles, params, include_pytrendline=include_pytrendline
    )
    consensus = snap.consensus
    window = list(candles[-params.window_bars :])
    detectors: dict = {}
    for name, ms in snap.by_detector.items():
        bars = int(ms.meta.get("bars") or len(window))
        det_series = window[-bars:]
        detectors[name] = {
            "structure_score": ms.structure_score,
            "support_zones": [_zone_dict(z) for z in ms.support_zones],
            "resistance_zones": [_zone_dict(z) for z in ms.resistance_zones],
            "support_trendlines": [_line_dict(t, det_series) for t in ms.support_trendlines],
            "resistance_trendlines": [
                _line_dict(t, det_series) for t in ms.resistance_trendlines
            ],
            "pivot_count": len(ms.pivots),
            "meta": ms.meta,
        }
    return {
        "symbol": symbol.upper(),
        "timeframe": timeframe,
        "provider": provider.id,
        "provider_symbol": provider_symbol,
        "atr": snap.atr,
        "last_close": snap.last_close,
        "distance_to_support": snap.distance_to_support,
        "distance_to_resistance": snap.distance_to_resistance,
        "consensus": {
            "structure_score": consensus.structure_score,
            "support_zones": [_zone_dict(z) for z in consensus.support_zones],
            "resistance_zones": [_zone_dict(z) for z in consensus.resistance_zones],
            "meta": consensus.meta,
        },
        "detectors": detectors,
        "breakout_candidates": [
            {
                "side": b.side.value,
                "confirmed": b.confirmed,
                "close": b.close,
                "distance_atr": b.distance_atr,
                "body_ratio": b.body_ratio,
                "rvol": b.rvol,
                "reason": b.reason,
                "zone": _zone_dict(b.zone),
            }
            for b in snap.breakout_candidates
        ],
    }
