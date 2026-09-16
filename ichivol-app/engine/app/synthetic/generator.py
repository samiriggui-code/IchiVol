"""Synthetic Market Generator (mission brief §11-13): deterministic, seeded
OHLCV fabrication for the Synthetic Market Lab. Its job is narrow -- turn a
named regime into a Candle series -- so IchiVol's real pipeline can be
pointed at market shapes whose "correct" interpretation is known in advance,
before ever trusting its read of noisy real data (see app/synthetic/scenarios.py
for the catalogued shapes and app/synthetic/validation.py for the comparison
against ground truth).

This module knows nothing about Ichimoku, RVOL, or the pipeline -- it only
produces prices and volumes. Same seed + same regime => byte-identical
output (tests/synthetic/test_generator.py proves this), which is what makes
a scenario's ground truth meaningful to compare against run to run.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from enum import Enum

from app.indicators.ichimoku import Candle


class Regime(str, Enum):
    BULLISH_TREND = "bullish_trend"  # brief scenario A
    BEARISH_TREND = "bearish_trend"  # brief scenario B
    FALSE_BREAKOUT = "false_breakout"  # brief scenario D
    LOW_VOLUME_BULLISH = "low_volume_bullish"  # brief scenario E
    RANGE = "range"  # brief scenario G


@dataclass(frozen=True)
class GeneratorParams:
    n: int = 300
    base_price: float = 100.0
    base_volume: float = 100.0
    seed: int = 42


def false_breakout_windows(n: int) -> tuple[int, int]:
    """Bar indices (consolidation_end, breakout_end) for Regime.FALSE_BREAKOUT
    at a given length -- exposed so app/synthetic/scenarios.py can point its
    ground truth's eval_window at the actual breakout without duplicating
    the arithmetic (and risking it drifting out of sync with the generator).
    """
    consolidation_end = int(n * 0.65)
    return consolidation_end, consolidation_end + 12


def generate_market(regime: Regime, params: GeneratorParams = GeneratorParams()) -> list[Candle]:
    rng = random.Random(params.seed)
    builders = {
        Regime.BULLISH_TREND: _bullish_trend,
        Regime.BEARISH_TREND: _bearish_trend,
        Regime.FALSE_BREAKOUT: _false_breakout,
        Regime.LOW_VOLUME_BULLISH: _low_volume_bullish,
        Regime.RANGE: _range,
    }
    closes, volumes = builders[regime](rng, params.n, params.base_price, params.base_volume)
    return _candles_from_closes(closes, volumes, rng, noise_amplitude=params.base_price * 0.003)


def _candles_from_closes(
    closes: list[float], volumes: list[float], rng: random.Random, noise_amplitude: float
) -> list[Candle]:
    candles: list[Candle] = []
    prev_close = closes[0]
    for i, close in enumerate(closes):
        open_ = prev_close
        high = max(open_, close) + rng.uniform(0.0, noise_amplitude)
        low = min(open_, close) - rng.uniform(0.0, noise_amplitude)
        # Floor kept vanishingly small (not the more natural-looking 1.0) so
        # it never clamps a deliberately-decaying volume path back up -- a
        # fixed floor breaks a pure geometric decay's RVOL-suppressing
        # property the moment the decay dips below it, silently
        # re-equilibrating RVOL back to ~1.0 (see _low_volume_bullish, whose
        # 300-bar 0.95**i decay is well below 1.0 by bar ~170).
        candles.append(Candle(time=i, open=open_, high=high, low=low, close=close, volume=max(1e-9, volumes[i])))
        prev_close = close
    return candles


def _bullish_trend(rng: random.Random, n: int, base_price: float, base_volume: float):
    closes = [base_price]
    volumes = [base_volume]
    for i in range(1, n):
        # Two competing constraints on drift and noise, both discovered
        # empirically by running this scenario through the real pipeline:
        # (1) noise must stay small relative to drift *accumulated over an
        # Ichimoku lookback window* (~9-26 bars) -- signal-to-noise for a
        # window w scales as (drift/noise_std) * sqrt(w), so with the old
        # noise_std=0.004 even a "clean" trend produced real local lower-lows
        # big enough to flip Tenkan<Kijun and structure to BEARISH mid-series
        # -- correctly detected by the engine, just not what this scenario's
        # ground truth (always-bullish) claimed to be testing; (2) drift
        # must not compound the raw price level too far over 300 bars,
        # because app/indicators/atr.py's regime percentile compares
        # *absolute* ATR to its own trailing 100-bar history (not ATR/price)
        # -- a violently compounding path inflates absolute ATR from price
        # growth alone and can drift itself into a false EXTREME regime with
        # no real volatility expansion behind it. Small drift + small noise
        # (mild ~+27% cumulative move, low per-bar noise) satisfies both.
        closes.append(closes[-1] * (1 + 0.0010 + rng.gauss(0.0, 0.0015)))
        up = closes[-1] > closes[-2]
        # Volume correlated with the direction of the move -- realistic, and
        # gives RVOL something to confirm on the up bars (brief scenario A
        # expects "normal or elevated" volume, not silence).
        volumes.append(base_volume * (1.15 if up else 0.85) * rng.uniform(0.85, 1.35))
    return closes, volumes


def _bearish_trend(rng: random.Random, n: int, base_price: float, base_volume: float):
    closes = [base_price]
    volumes = [base_volume]
    for i in range(1, n):
        closes.append(closes[-1] * (1 - 0.0018 + rng.gauss(0.0, 0.004)))
        down = closes[-1] < closes[-2]
        volumes.append(base_volume * (1.15 if down else 0.85) * rng.uniform(0.85, 1.35))
    return closes, volumes


def _range(rng: random.Random, n: int, base_price: float, base_volume: float):
    amplitude = base_price * 0.03
    closes = [
        base_price + amplitude * math.sin(i / 11.0) + rng.gauss(0.0, base_price * 0.0025) for i in range(n)
    ]
    volumes = [base_volume * rng.uniform(0.8, 1.2) for _ in range(n)]
    return closes, volumes


def _low_volume_bullish(rng: random.Random, n: int, base_price: float, base_volume: float):
    closes = [base_price]
    volumes = [base_volume * 0.5]
    for i in range(1, n):
        closes.append(closes[-1] * (1 + 0.0006 + rng.gauss(0.0, 0.004)))
        # A pure (unfloored) geometric decay, not a decay-then-plateau: for
        # v_i = V0 * r**i, a trailing moving average lags behind by a
        # constant multiple of v_i regardless of i, so v_i/avg_i (= RVOL)
        # stays a suppressed constant ratio for as long as the decay
        # continues uninterrupted. r=0.95 against a 20-bar window keeps that
        # ratio around ~0.59 (comfortably under RvolParams.low_threshold's
        # default 0.7 => AnomalyLevel.LOW), matching the rate already proven
        # to work this way in tests/backtest/test_experiments.py's
        # `_uptrend_with_flat_low_volume` fixture. A gentler rate (tried
        # 0.985 first) only suppresses RVOL to ~0.87 -- still "NORMAL", not
        # "LOW" -- so it silently fails to gate participation at all.
        volumes.append(base_volume * 0.5 * (0.95**i) * rng.uniform(0.9, 1.1))
    return closes, volumes


def _false_breakout(rng: random.Random, n: int, base_price: float, base_volume: float):
    consolidation_end, breakout_end = false_breakout_windows(n)
    resistance = base_price * 1.03
    closes: list[float] = []
    volumes: list[float] = []
    for i in range(n):
        if i < consolidation_end:
            closes.append(base_price + base_price * 0.015 * math.sin(i / 9.0) + rng.gauss(0.0, base_price * 0.002))
            volumes.append(base_volume * rng.uniform(0.8, 1.1))
        elif i < breakout_end:
            # Pokes above resistance, but on thin volume -- the giveaway
            # that this breakout has no real participation behind it.
            progress = (i - consolidation_end) / max(1, breakout_end - consolidation_end)
            closes.append(resistance * (1 + 0.01 * progress) + rng.gauss(0.0, base_price * 0.002))
            volumes.append(base_volume * rng.uniform(0.4, 0.65))
        else:
            # Snaps back below the range -- the "false" part of the breakout.
            closes.append(base_price * 0.985 + rng.gauss(0.0, base_price * 0.0025))
            volumes.append(base_volume * rng.uniform(0.8, 1.3))
    return closes, volumes
