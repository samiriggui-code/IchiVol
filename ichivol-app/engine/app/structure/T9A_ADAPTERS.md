"""Adapter-specific behaviour retained after T9a shared causal pivots.

The fractal *core* lives in ``app.indicators.pivots``. Each Market Structure
adapter (and Fib / pipeline structure) keeps the following on top:

MVPP (``adapters/mvpp.py``)
  - Volume-adaptive wick/body price series (``_adaptive_prices``)
  - Prominence → quality, ``is_high_volume``, dedup by ``bar_index``
  - Trendline fit / zone scoring (no volume double-count with RVOL)

trendln (``adapters/trendln.py``)
  - Horizontal clustering + geometric diagonals
  - Default lookback 5 (symmetric)

pytrendline (``adapters/pytrendline.py``)
  - Provisional first/last anchors (``provisional=True``, may repaint)
  - ``allow_provisional_anchors`` / ``fit_pivot_bars`` / offline bar cap

Pipeline structure (``indicators/structure.py``)
  - HH/HL bias + BOS on top of raw OHLC fractals (default lookback 2)
  - Emits per-bar ``StructureState``, not a pivot list

Fibonacci (``fibonacci/context.py``)
  - Impulse selection + Fib ratios / confluence gate
  - Default left/right = 2 (historical; not MVPP's 5)

No CHoCH / FVG in T9a.
"""
