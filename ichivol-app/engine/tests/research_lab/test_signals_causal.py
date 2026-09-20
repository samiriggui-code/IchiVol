"""compute_bar_signals(bar i) must depend on candles[0..i] only (and closed HTF bars only)."""
import random

from app.indicators.ichimoku import Candle
from research_lab.signals import compute_bar_signals


def walk(n, step, seed):
    r = random.Random(seed)
    px, out = 100.0, []
    for i in range(n):
        o = px
        px *= 1 + r.gauss(0, 0.01)
        hi, lo = max(o, px) * 1.003, min(o, px) * 0.997
        out.append(Candle(time=1_700_000_000 - 1_700_000_000 % step + i * step, open=o, high=hi, low=lo, close=px,
                          volume=1000 + r.random() * 500, taker_buy_volume=500.0))
    return out


def test_prefix_equals_full_history():
    c1 = walk(700, 3600, 1)
    c4 = walk(175, 14400, 2)
    c4 = [Candle(time=c1[0].time + i * 14400, open=x.open, high=x.high, low=x.low, close=x.close, volume=x.volume,
                 taker_buy_volume=x.taker_buy_volume) for i, x in enumerate(c4)]
    full = compute_bar_signals(c1, c4)
    for k in (300, 450, 699):
        part = compute_bar_signals(c1[: k + 1], [b for b in c4 if b.time + 14400 <= c1[k].time])
        a, b = part[-1], full[k]
        assert (a.decision, a.direction, a.failed, a.mtf_aligned) == (b.decision, b.direction, b.failed, b.mtf_aligned)
