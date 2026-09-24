"""T9b — CHoCH + break quality; legacy bos_* bit-identical; anti-lookahead."""

from __future__ import annotations

from app.indicators.ichimoku import Candle
from app.indicators.structure import (
    BosEvent,
    BreakQuality,
    StructureBias,
    StructureEventType,
    StructureParams,
    compute_structure,
)
from tests.indicators.test_ichimoku_lookahead import _make_candles


def _candles(ohlc: list[tuple[float, float, float, float]]) -> list[Candle]:
    return [
        Candle(time=i, open=o, high=h, low=lo, close=c, volume=100.0)
        for i, (o, h, lo, c) in enumerate(ohlc)
    ]


def test_legacy_bos_bullish_bit_identical_on_seed():
    """bos field must match a pure close-cross reference (pre-T9b)."""
    candles = _make_candles(150, seed=23)
    params = StructureParams(swing_lookback=2)
    got = compute_structure(candles, params)

    # Inline legacy close-cross only (no event / CHoCH).
    k = 2
    last_high = last_low = prev_high = prev_low = None
    bias = StructureBias.UNKNOWN
    for i, g in enumerate(got):
        j = i - k
        if j - k >= 0:
            window = candles[j - k : j + k + 1]
            highs = [c.high for c in window]
            lows = [c.low for c in window]
            if candles[j].high == max(highs):
                prev_high, last_high = last_high, candles[j].high
            if candles[j].low == min(lows):
                prev_low, last_low = last_low, candles[j].low
            if prev_high is not None and prev_low is not None:
                if last_high > prev_high and last_low > prev_low:
                    bias = StructureBias.BULLISH
                elif last_high < prev_high and last_low < prev_low:
                    bias = StructureBias.BEARISH
                else:
                    bias = StructureBias.MIXED
        bos = BosEvent.UNKNOWN
        if last_high is not None and last_low is not None and i > 0:
            close = candles[i].close
            prev_close = candles[i - 1].close
            if prev_close <= last_high < close:
                bos = BosEvent.BULLISH
            elif prev_close >= last_low > close:
                bos = BosEvent.BEARISH
            else:
                bos = BosEvent.NONE
        assert g.bos == bos
        assert g.bias == bias


def test_wick_break_is_not_close_and_not_legacy_bos():
    """Mèche above level with close back below → wick; bos stays NONE."""
    # Build swings then a wick pierce of last high without close beyond.
    ohlc = [
        (100, 102, 98, 100),
        (100, 105, 99, 104),
        (104, 110, 103, 108),  # peak ~110
        (108, 109, 100, 102),
        (102, 103, 95, 97),  # trough ~95
        (97, 104, 96, 103),
        (103, 106, 100, 105),  # confirms swings
        (105, 112, 104, 106),  # high 112 > last high, close 106 still below/at
    ]
    states = compute_structure(_candles(ohlc), StructureParams(swing_lookback=2))
    # Find a wick event
    wick_bars = [
        s
        for s in states
        if s.event is not None and s.event.break_quality == BreakQuality.WICK
    ]
    assert wick_bars, "expected at least one wick break"
    for s in wick_bars:
        assert s.bos in (BosEvent.NONE, BosEvent.UNKNOWN)
        assert s.event.break_quality == BreakQuality.WICK


def test_choch_when_break_against_bias():
    """Bullish close-break while bias is BEARISH → CHOCH bullish."""
    ohlc = [
        (100, 105, 99, 104),
        (104, 110, 103, 108),
        (108, 130, 107, 125),  # H1=130
        (125, 126, 115, 118),
        (118, 120, 110, 112),
        (112, 114, 100, 102),  # L1=100
        (102, 108, 101, 106),
        (106, 110, 104, 108),
        (108, 122, 107, 120),  # H2=122 LH
        (120, 121, 112, 114),
        (114, 116, 95, 98),  # L2=95 LL
        (98, 102, 96, 100),
        (100, 104, 99, 103),  # confirm L2 → BEARISH
        (103, 125, 102, 124),  # close breaks 122 → CHOCH bullish
    ]
    params = StructureParams(
        swing_lookback=2,
        confirm_bars=5,
        confirm_displacement_atr=100.0,
    )
    states = compute_structure(_candles(ohlc), params)
    choch = [
        s
        for s in states
        if s.event is not None
        and s.event.type == StructureEventType.CHOCH
        and s.event.direction == "bullish"
    ]
    assert choch, "expected CHOCH bullish against bearish bias"
    assert choch[-1].bias == StructureBias.BEARISH
    assert any(s.bos == BosEvent.BULLISH for s in states)


def test_confirmed_never_before_confirmation_bar():
    """A confirmed break is unknown on any prefix ending before confirm bar."""
    candles = _make_candles(120, seed=9)
    params = StructureParams(
        swing_lookback=2,
        confirm_bars=2,
        confirm_displacement_atr=1e9,  # force bar-count path only
    )
    full = compute_structure(candles, params)
    confirmed = [
        s for s in full if s.event is not None and s.event.break_quality == BreakQuality.CONFIRMED
    ]
    if not confirmed:
        # Force a synthetic series with known confirm
        ohlc = [
            (100, 102, 98, 100),
            (100, 105, 99, 104),
            (104, 110, 103, 108),
            (108, 109, 100, 102),
            (102, 103, 95, 97),
            (97, 104, 96, 103),
            (103, 106, 100, 105),
            (105, 116, 104, 115),  # close break
            (115, 117, 114, 116),  # subsequent beyond #1
            (116, 118, 115, 117),  # subsequent beyond #2 → confirmed
        ]
        candles = _candles(ohlc)
        full = compute_structure(candles, params)
        confirmed = [
            s
            for s in full
            if s.event is not None and s.event.break_quality == BreakQuality.CONFIRMED
        ]
    assert confirmed, "need at least one confirmed event for anti-lookahead"
    for s in confirmed:
        cbar = s.event.bar
        # Prefix ending at cbar (length cbar) excludes bar cbar
        trunc = compute_structure(candles[:cbar], params)
        assert not any(
            t.event is not None
            and t.event.break_quality == BreakQuality.CONFIRMED
            and t.event.level == s.event.level
            and t.event.direction == s.event.direction
            for t in trunc
        )
        # At confirmation bar inclusive
        full_to = compute_structure(candles[: cbar + 1], params)
        assert any(
            t.event is not None
            and t.event.break_quality == BreakQuality.CONFIRMED
            and t.event.bar == cbar
            for t in full_to
        )


def test_confirm_params_are_explicit_not_magic():
    p = StructureParams()
    assert isinstance(p.confirm_bars, int)
    assert isinstance(p.confirm_displacement_atr, float)
