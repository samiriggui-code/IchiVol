"""Parameters for Market Structure engines (ATR-normalized where possible)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class StructureEngineParams:
    # Shared
    atr_period: int = 14
    zone_atr_mult: float = 0.35
    """Half-width of a zone around a level = ATR * zone_atr_mult."""
    max_lines_per_side: int = 5
    min_touches: int = 3
    window_bars: int = 300
    """Hard cap on bars fed to detectors (screener safety)."""

    # MVPP-inspired (clean-room; volume used for wick/body only — NOT line score)
    fractal_left: int = 5
    fractal_right: int = 5
    vol_sma_lookback: int = 20
    high_vol_mult: float = 1.5
    touch_atr_mult: float = 0.25
    include_volume_in_line_score: bool = False
    """Keep False to avoid double-counting with RVOL in confluence."""

    # trendln-inspired
    extrema_lookback: int = 5
    horizontal_min_touches: int = 2

    # pytrendline-inspired (offline)
    pytrendline_max_bars: int = 150
    pytrendline_offline_only: bool = True
    breakout_atr_mult: float = 0.15
    max_pt_error_atr_mult: float = 0.12
    allow_provisional_anchors: bool = False
    """If True, first/last window anchors may fit trendlines (legacy repaint).

    Default False (T1f-2): only confirmed fractals fit lines. Never enable in
    live paper profiles — tests / A-B comparison only.
    """

    # Consensus
    consensus_atr_mult: float = 0.5
    min_detectors_agree: int = 1
