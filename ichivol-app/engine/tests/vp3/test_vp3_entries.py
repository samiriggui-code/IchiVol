"""VP3 entry masks — B0/B1/B2 event rules on synthetic closed candles."""

from __future__ import annotations

from app.indicators.ichimoku import Candle
from research_lab.sim import CostModel, simulate
from vp2 import BAR_SECONDS
from vp3 import RVOL_MIN, WARMUP_BARS
from vp3.entries import b1_trigger, entry_mask, htf_cloud_direction
from vp3.rules import strategy_rules
from app.indicators.ichimoku import IchimokuParams, compute_ichimoku
from app.indicators.rvol import RvolParams, compute_rvol

H = 3600
T0 = 1_700_000_000 - 1_700_000_000 % H
NOFEE = CostModel("nofee", 0.0, 0.0, 0.0)


def candles_flat(n: int, px: float = 100.0, vol: float = 1000.0) -> list[Candle]:
    return [
        Candle(time=T0 + i * H, open=px, high=px + 1, low=px - 1, close=px, volume=vol)
        for i in range(n)
    ]


def test_b0_single_entry_after_warmup_hold_to_end():
    n = WARMUP_BARS + 10
    candles = candles_flat(n)
    mask = entry_mask("B0", candles)
    assert sum(mask) == 1
    assert mask[WARMUP_BARS] is True
    assert all(not m for i, m in enumerate(mask) if i != WARMUP_BARS)

    # Wire into sim via decisions
    from research_lab.signals import BarSignal
    from app.agents.types import Direction
    from app.indicators.atr import compute_atr

    atr = compute_atr(candles)
    feed = {}
    for i, c in enumerate(candles):
        sd = atr[i].suggested_stop_distance
        d = "BUY" if mask[i] else "WATCH"
        feed[c.time] = (
            c,
            BarSignal(
                c.time,
                d,
                Direction.LONG if d == "BUY" else Direction.NEUTRAL,
                float(sd) if sd else 1.0,
                None,
                (),
                (),
                "signal",
                None,
            ),
        )
    rules = strategy_rules("B0", "1h")
    assert rules.exit_mode == "hold" and rules.time_stop_bars is None
    res = simulate({"X": feed}, rules, NOFEE, (T0, T0 + n * H), initial=10_000.0)
    assert len(res.trades) == 1
    assert res.trades[0].exit_reason == "window_end"


def test_b1_needs_tk_cross_and_cloud():
    # Build a path where TK crosses up while price is above a formed cloud
    # Use enough bars for warm-up then force a cross via price structure
    n = WARMUP_BARS + 5
    rows = []
    for i in range(n):
        # Uptrend late so tenkan > kijun after being below
        if i < WARMUP_BARS - 2:
            px = 100.0 + i * 0.01
        elif i == WARMUP_BARS - 2:
            px = 100.0  # pull tenkan down relative to kijun
        elif i == WARMUP_BARS - 1:
            px = 90.0
        else:
            px = 130.0 + (i - WARMUP_BARS)  # strong push → tenkan crosses up, above cloud
        rows.append(
            Candle(
                time=T0 + i * H,
                open=px,
                high=px + 2,
                low=px - 2,
                close=px,
                volume=1000.0,
            )
        )
    ichi = compute_ichimoku(rows, IchimokuParams())
    # At least one index should satisfy the formal trigger OR we assert the helper components
    triggers = [b1_trigger(ichi, rows, i) for i in range(len(rows))]
    # Formal properties on any True trigger
    for i, ok in enumerate(triggers):
        if not ok:
            continue
        assert ichi[i].tenkan is not None and ichi[i].kijun is not None
        assert ichi[i - 1].tenkan <= ichi[i - 1].kijun
        assert ichi[i].tenkan > ichi[i].kijun
        assert rows[i].close > max(ichi[i].senkou_a, ichi[i].senkou_b)
    mask = entry_mask("B1", rows)
    assert len(mask) == n
    assert all(not mask[i] for i in range(WARMUP_BARS))


def test_b2_requires_rvol_gate():
    n = WARMUP_BARS + 3
    # Flat volume → rvol ~ 1.0 < 1.5 so B2 should be empty even if B1 fires
    candles = candles_flat(n, vol=1000.0)
    # Spike volume on last bars won't create TK cross on flat prices; just check rvol math
    rvol = compute_rvol(candles, RvolParams(primary_window=20, significant_threshold=RVOL_MIN))
    assert rvol[-1].rvol20 is not None
    assert rvol[-1].rvol20 < RVOL_MIN
    mask_b2 = entry_mask("B2", candles)
    assert not any(mask_b2)


def test_htf_cloud_direction_helper():
    class _Row:
        senkou_a = 100.0
        senkou_b = 90.0

    assert htf_cloud_direction(_Row(), 110.0) == "long"
    assert htf_cloud_direction(_Row(), 80.0) == "short"
    assert htf_cloud_direction(_Row(), 95.0) == "neutral"


def test_b1_b2_rules_use_levels_only():
    r = strategy_rules("B1", "1h")
    assert r.exit_mode == "levels_only"
    assert r.time_stop_bars == 48
    assert r.allow_short is False
    r4 = strategy_rules("B5", "4h")
    assert r4.time_stop_bars == 24
    assert BAR_SECONDS["4h"] == r4.bar_seconds
