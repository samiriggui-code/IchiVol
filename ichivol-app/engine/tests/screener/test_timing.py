"""Hour-boundary, late-arrival and staleness behaviour of closed-candle signals."""

from datetime import datetime, timezone

from app.indicators.ichimoku import Candle
from app.screener import service
from app.screener.timing import compute_signal_timing

H = 3600


def ts(h, m=0, s=0):
    return int(datetime(2026, 9, 20, h, m, s, tzinfo=timezone.utc).timestamp())


def bars_until(last_open_hour):
    """Provider bars: opens at 05:00 .. last_open_hour:00 (last one may still be forming)."""
    return [Candle(time=ts(h), open=1, high=2, low=1, close=1.5) for h in range(5, last_open_hour + 1)]


def test_before_and_after_the_hour_boundary():
    # 09:59:50 -> the 09:00 bar is still forming; last closed = 08:00 (closes 09:00)
    now = ts(9, 59, 50)
    used = service._closed_only(bars_until(9), "1h", now=now)
    t = compute_signal_timing(used, H, now, 1.6, "1h", True)
    assert used[-1].time == ts(8) and t.signal_bar_close == ts(9) and t.lag_bars == 0 and not t.stale

    # 10:00:20 -> provider already has the new 10:00 (forming) bar; 09:00 is now closed and used
    now = ts(10, 0, 20)
    used = service._closed_only(bars_until(10), "1h", now=now)
    t = compute_signal_timing(used, H, now, 1.6, "1h", True)
    assert used[-1].time == ts(9) and t.signal_bar_close == ts(10) and t.lag_bars == 0


def test_late_arrival_of_the_new_close_is_flagged_after_grace():
    # 10:00:20 but provider has not produced the 10:00 bar yet: its last bar is 09:00 (forming/closed?)
    now = ts(10, 0, 20)
    provider = bars_until(9)  # newest = 09:00 bar, which closed at 10:00
    used = service._closed_only(provider, "1h", now=now)
    assert used[-1].time == ts(9)  # closed by the clock even without the 10:00 forming bar
    # provider missing the 09:00 bar itself (delivery lag): last available is 08:00
    used2 = service._closed_only(bars_until(8), "1h", now=now)
    t = compute_signal_timing(used2, H, now, 1.6, "1h", True)
    assert t.lag_bars == 1 and not t.data_late  # within delivery grace (20 s after the boundary)
    t2 = compute_signal_timing(used2, H, ts(10, 5), 1.6, "1h", True)
    assert t2.lag_bars == 1 and t2.data_late and not t2.stale  # 5 min late: flagged, not yet stale


def test_stale_after_two_missing_closes_and_intent_refuses():
    now = ts(12, 30)
    used = service._closed_only(bars_until(9), "1h", now=now)  # provider stuck at 09:00
    t = compute_signal_timing(used, H, now, 1.6, "1h", True)
    assert t.stale and t.lag_bars >= 2

    from types import SimpleNamespace
    from app.agents.types import Direction
    from app.decision.pipeline import PipelineResult
    from app.paper.intent import propose_order_intent

    row = SimpleNamespace(
        symbol="X", timeframe="1h", price=1.6, candles=[], evidence=None, atr=SimpleNamespace(suggested_stop_distance=0.1),
        pipeline=PipelineResult(decision="BUY", direction=Direction.LONG, stages=[]), signal_timing=t.to_dict(),
    )
    intent = propose_order_intent(None, row)  # refuses before touching the DB
    assert intent.actionable is False and intent.reason == "stale_data"
    assert intent.signal_timing["stale"] is True
