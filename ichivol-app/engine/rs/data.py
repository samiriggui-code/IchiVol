"""Chargement VP1 4h tronqué < 2025-01-01 (RS-03 §1)."""

from __future__ import annotations

from pathlib import Path

from app.indicators.ichimoku import Candle
from vp2.data import bars_to_candles, load_vp1_spot

from rs import DATA_END_EXCL, INTERVAL


def truncate(candles: list[Candle], end_excl: int = DATA_END_EXCL) -> list[Candle]:
    out = [c for c in candles if c.time < end_excl]
    assert_no_reserved(out, end_excl)
    return out


def assert_no_reserved(candles: list[Candle], end_excl: int = DATA_END_EXCL) -> None:
    """Garde-fou : aucune barre de la validation 2025 / holdout 2026 ne doit atteindre la stratégie."""
    bad = [c.time for c in candles if c.time >= end_excl]
    if bad:
        raise AssertionError(f"{len(bad)} barre(s) >= 2025-01-01 transmises à la stratégie")


def load_symbol(
    symbol: str, root: Path | None = None, end_excl: int = DATA_END_EXCL
) -> tuple[list[Candle], str]:
    payload, digest = load_vp1_spot(root, symbol, INTERVAL)
    return truncate(bars_to_candles(payload["bars"]), end_excl), digest
