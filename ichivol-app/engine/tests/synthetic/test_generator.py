from __future__ import annotations

from app.synthetic.generator import GeneratorParams, Regime, generate_market


def test_same_seed_produces_byte_identical_candles():
    params = GeneratorParams(n=100, seed=7)
    a = generate_market(Regime.BULLISH_TREND, params)
    b = generate_market(Regime.BULLISH_TREND, params)
    assert a == b


def test_different_seeds_produce_different_paths():
    a = generate_market(Regime.BULLISH_TREND, GeneratorParams(n=100, seed=1))
    b = generate_market(Regime.BULLISH_TREND, GeneratorParams(n=100, seed=2))
    assert [c.close for c in a] != [c.close for c in b]


def test_bullish_trend_nets_higher_highs_and_higher_lows():
    candles = generate_market(Regime.BULLISH_TREND, GeneratorParams(n=200, seed=1))
    first_quarter = candles[:50]
    last_quarter = candles[-50:]
    avg_close = lambda cs: sum(c.close for c in cs) / len(cs)
    assert avg_close(last_quarter) > avg_close(first_quarter)


def test_bearish_trend_nets_lower_closes():
    candles = generate_market(Regime.BEARISH_TREND, GeneratorParams(n=200, seed=1))
    first_quarter = candles[:50]
    last_quarter = candles[-50:]
    avg_close = lambda cs: sum(c.close for c in cs) / len(cs)
    assert avg_close(last_quarter) < avg_close(first_quarter)


def test_range_market_has_no_net_drift():
    candles = generate_market(Regime.RANGE, GeneratorParams(n=300, seed=7))
    first_quarter = candles[:50]
    last_quarter = candles[-50:]
    avg_close = lambda cs: sum(c.close for c in cs) / len(cs)
    # Oscillating around the same mean -- allow generous noise tolerance,
    # this only needs to rule out a directional trend slipping in.
    assert abs(avg_close(last_quarter) - avg_close(first_quarter)) < 5.0


def test_low_volume_bullish_never_expands_volume():
    candles = generate_market(Regime.LOW_VOLUME_BULLISH, GeneratorParams(n=300, seed=5, base_volume=100.0))
    assert max(c.volume for c in candles) < 100.0  # never reaches, let alone exceeds, base_volume


def test_false_breakout_reverts_below_the_pre_breakout_range():
    from app.synthetic.generator import false_breakout_windows

    candles = generate_market(Regime.FALSE_BREAKOUT, GeneratorParams(n=300, seed=4))
    consolidation_end, breakout_end = false_breakout_windows(300)
    pre_breakout_avg = sum(c.close for c in candles[:consolidation_end]) / consolidation_end
    breakout_peak = max(c.close for c in candles[consolidation_end:breakout_end])
    post_breakout_avg = sum(c.close for c in candles[breakout_end : breakout_end + 20]) / 20

    assert breakout_peak > pre_breakout_avg  # the poke above resistance happened
    assert post_breakout_avg < pre_breakout_avg  # and it didn't hold
