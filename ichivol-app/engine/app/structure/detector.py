"""StructureDetector protocol."""

from __future__ import annotations

from typing import Protocol, Sequence

from app.indicators.ichimoku import Candle
from app.structure.params import StructureEngineParams
from app.structure.types import MarketStructure


class StructureDetector(Protocol):
    """Adapter contract — IchiVol stays free of external repo imports."""

    name: str

    def detect(
        self,
        candles: Sequence[Candle],
        params: StructureEngineParams = ...,
        *,
        atr: float | None = None,
    ) -> MarketStructure: ...
