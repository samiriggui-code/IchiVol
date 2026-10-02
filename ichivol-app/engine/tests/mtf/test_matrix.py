"""MTF-1 — matrice multi-horizons : causalité, états, relations, phrase, lecture portefeuille, cache."""

from __future__ import annotations

import random
from datetime import datetime, timezone

import pytest

from app.indicators.ichimoku import Candle
from app.mtf import service as mtf_service
from app.mtf.matrix import (
    HORIZON_SECONDS,
    HorizonState,
    Relation,
    compute_mtf_matrix,
    describe,
    horizons_for,
    portfolio_reading,
    read_horizon,
)

MONDAY = int(datetime(2026, 9, 21, tzinfo=timezone.utc).timestamp())  # aligned on every tf incl. 1w


def trend(tf: str, n: int, *, end_open: int, slope: float, seed: int = 1, forming: bool = True) -> list[Candle]:
    """n bars ending with the bar that opens at ``end_open`` (forming when ``forming``)."""
    tf_s = HORIZON_SECONDS[tf]
    rng = random.Random(seed)
    price = 100.0
    out = []
    for i in range(n):
        t = end_open - (n - 1 - i) * tf_s
        o = price
        c = max(1.0, price + slope + rng.uniform(-0.3, 0.3))
        out.append(Candle(time=t, open=o, high=max(o, c) + 0.2, low=min(o, c) - 0.2, close=c,
                          volume=rng.uniform(50, 150)))
        price = c
    return out if forming else out


def test_horizons_always_include_decision_tf_sorted():
    assert horizons_for("1h") == ["1h", "4h", "1d", "1w"]
    assert horizons_for("15m") == ["15m", "1h", "4h", "1d", "1w"]


def test_reading_is_truncation_stable_and_never_uses_future_bars():
    now = MONDAY + 30 * 60  # 00:30 — the 00:00 1h bar is forming
    bars = trend("1h", 200, end_open=MONDAY + 5 * 3600, slope=0.5)  # 5 bars beyond `now` (future)
    a = read_horizon(bars, "1h", now=now)
    b = read_horizon([c for c in bars if c.time <= now], "1h", now=now)
    assert a == b
    assert a.bar_close == MONDAY and a.bar_close <= now  # last CLOSED bar, the forming one excluded


def test_forming_bar_never_changes_the_confirmed_direction():
    now = MONDAY + 30 * 60
    bars = trend("1h", 200, end_open=MONDAY, slope=0.5)
    crash = bars[:-1] + [Candle(time=MONDAY, open=bars[-1].open, high=bars[-1].open, low=1.0, close=1.0, volume=1e6)]
    base, shocked = read_horizon(bars, "1h", now=now), read_horizon(crash, "1h", now=now)
    assert base.direction == shocked.direction == "LONG"
    assert shocked.provisional_direction != "LONG"  # shown apart, labelled provisional
    assert shocked.provisional_bar_open == MONDAY


def test_higher_horizon_bar_is_used_only_after_its_close():
    # 03:59 on Monday: the 00:00 4h bar is still forming → last closed 4h bar closed at 00:00.
    now = MONDAY + 4 * 3600 - 60
    r = read_horizon(trend("4h", 200, end_open=MONDAY, slope=0.5), "4h", now=now)
    assert r.bar_close == MONDAY
    r2 = read_horizon(trend("4h", 200, end_open=MONDAY + 4 * 3600, slope=0.5), "4h", now=MONDAY + 4 * 3600 + 5)
    assert r2.bar_close == MONDAY + 4 * 3600


def test_states_unavailable_late_stale_and_weekly_confirmed():
    now = MONDAY + 30 * 60
    assert read_horizon(None, "4h", now=now, unavailable_reason="provider_error").unavailable_reason == "provider_error"
    short = read_horizon(trend("1d", 40, end_open=MONDAY, slope=0.5), "1d", now=now)
    assert short.state == HorizonState.UNAVAILABLE and short.unavailable_reason == "insufficient_history"
    # 1h series whose last bar opened 3h before `now` → stale
    stale = read_horizon(trend("1h", 200, end_open=MONDAY - 3 * 3600, slope=0.5), "1h", now=now)
    assert stale.state == HorizonState.STALE
    late = read_horizon(trend("1h", 200, end_open=MONDAY - 2 * 3600, slope=0.5), "1h", now=now)
    assert late.state == HorizonState.LATE
    weekly = read_horizon(trend("1w", 120, end_open=MONDAY, slope=0.5), "1w", now=MONDAY + 2 * 86400)
    assert weekly.state == HorizonState.CONFIRMED and weekly.bar_close == MONDAY


def _matrix(slopes: dict[str, float | None], decision_tf: str = "1h"):
    now = MONDAY + 30 * 60
    series = {tf: (trend(tf, 200, end_open=MONDAY, slope=s) if s is not None else None) for tf, s in slopes.items()}
    return compute_mtf_matrix(series, symbol="btcusdt", decision_tf=decision_tf, now=now,
                              unavailable_reasons={"1w": "provider_no_timeframe"})


def test_relations_and_summary_counts():
    m = _matrix({"1h": 0.5, "4h": -0.5, "1d": -0.5, "1w": None})
    assert m.symbol == "BTCUSDT"
    rel = {h.timeframe: h.relation for h in m.horizons}
    assert rel == {"1h": Relation.SELF, "4h": Relation.OPPOSED, "1d": Relation.OPPOSED, "1w": Relation.UNKNOWN}
    s = m.summary
    assert (s.decision_direction, s.parent_tf, s.parent_relation) == ("LONG", "4h", "opposed")
    assert s.opposed == ["4h", "1d"] and s.unknown == ["1w"] and s.aligned == []
    assert (s.n_available, s.n_horizons) == (3, 4)
    assert m.horizon("1w").unavailable_reason == "provider_no_timeframe"
    d = m.to_dict()
    assert d["observe_only"] is True and d["used_by_decision"] is False


def test_describe_reuses_real_pipeline_stages():
    m = _matrix({"1h": 0.5, "4h": -0.5, "1d": 0.5, "1w": 0.5})
    pipeline = {
        "decision": "WATCH",
        "direction": "LONG",
        "stages": [
            {"id": "direction", "status": "pass", "codes": []},
            {"id": "participation", "status": "fail", "codes": ["rvol_low"]},
            {"id": "structure", "status": "watch", "codes": ["mtf_opposed"]},
        ],
    }
    text = describe(m, pipeline)
    assert text.startswith("Tendance 1h haussière (bougie close 21/09 00:00 UTC)")
    assert "contexte 4h baissier, 1d haussier, 1w haussier" in text
    assert "entrée non confirmée (Participation en échec : rvol_low ; Structure en surveillance : mtf_opposed)" in text
    assert describe(m).endswith(".")  # without pipeline: no decision claim
    m2 = _matrix({"1h": 0.5, "4h": -0.5, "1d": 0.5, "1w": None})
    assert "1w indisponible (non servi par la source)" in describe(m2)


def test_portfolio_reading_follows_the_real_exit_rule():
    prof = {"allow_short": False, "exit_mode": "direction", "auto_timeframes": ["1h"]}
    sell = {"decision": "SELL", "direction": "SHORT"}
    txt = portfolio_reading(sell, timeframe="1h", profile=prof, open_long_on_tf=True)
    assert "aucune ouverture short" in txt and "sera fermée au prochain cycle" in txt
    # NEUTRAL direction (WATCH) also closes an auto long under exit_mode=direction
    neutral = portfolio_reading({"decision": "WATCH", "direction": "NEUTRAL"}, timeframe="1h", profile=prof)
    assert "serait fermée s'il y en a une (direction NEUTRAL)" in neutral
    keep = portfolio_reading({"decision": "WATCH", "direction": "LONG"}, timeframe="1h", profile=prof)
    assert "conservée (direction toujours LONG)" in keep
    other_tf = portfolio_reading({"decision": "BUY", "direction": "LONG"}, timeframe="4h", profile=prof)
    assert "pas d'ouverture automatique en 4h" in other_tf
    none = portfolio_reading(sell, timeframe="1h", profile=prof, open_long_on_tf=False)
    assert "aucune position longue automatique en 1h à fermer" in none


class _FakeProvider:
    def __init__(self, pid="binance"):
        self.id = pid
        self.calls: list[str] = []

    def fetch_ohlcv(self, symbol, timeframe, limit=300):
        self.calls.append(timeframe)
        return trend(timeframe, 200, end_open=MONDAY, slope=0.5)


def test_cache_refetches_only_after_the_next_close():
    mtf_service.clear_cache()
    p = _FakeProvider()
    now = MONDAY + 60
    mtf_service.fetch_horizon(p, "BTCUSDT", "BTCUSDT", "4h", now=now)
    mtf_service.fetch_horizon(p, "BTCUSDT", "BTCUSDT", "4h", now=now + 600)
    assert p.calls == ["4h"]
    mtf_service.fetch_horizon(p, "BTCUSDT", "BTCUSDT", "4h", now=MONDAY + 4 * 3600 + 1)
    assert p.calls == ["4h", "4h"]


def test_collect_series_reasons_per_provider():
    mtf_service.clear_cache()
    series, reasons = mtf_service.collect_series(_FakeProvider("twelve_data"), "AAPL", "AAPL", "1h", now=MONDAY,
                                                 decision_candles=trend("1h", 200, end_open=MONDAY, slope=0.5))
    assert series["1h"] is not None and series["4h"] is None
    assert reasons == {"4h": "provider_credit_budget", "1d": "provider_credit_budget", "1w": "provider_credit_budget"}
    _, reasons = mtf_service.collect_series(_FakeProvider("biquote"), "EURUSD", "EURUSD", "1h", now=MONDAY,
                                            decision_candles=[])
    assert reasons == {"1w": "provider_no_timeframe"}


def test_matrix_for_scan_never_raises():
    class _Broken:
        id = "binance"

        def fetch_ohlcv(self, *a, **k):
            raise RuntimeError("boom")

    mtf_service.clear_cache()
    m = mtf_service.matrix_for_scan(_Broken(), "BTCUSDT", "BTCUSDT", "1h",
                                    trend("1h", 200, end_open=MONDAY, slope=0.5), now=MONDAY + 60)
    assert m is not None and m.horizon("4h").unavailable_reason == "provider_error"
    assert m.horizon("1h").state == HorizonState.CONFIRMED


@pytest.mark.parametrize("closed_only", [True])
def test_scan_symbol_matrix_matches_pipeline_direction(monkeypatch, closed_only):
    """Cohérence : la ligne de décision de la matrice = la direction du pipeline (même bougies closes)."""
    from app.config import settings
    from app.market_data import binance_futures
    from app.screener import service

    monkeypatch.setattr(settings, "decide_on_closed_candles", closed_only)
    monkeypatch.setattr(binance_futures, "fetch_open_interest_hist", lambda *a, **k: [])
    monkeypatch.setattr(binance_futures, "fetch_funding_rate_hist", lambda *a, **k: [])
    import time as _time

    now = int(_time.time())
    end_open = now - now % 3600
    provider = _FakeProvider()
    provider.fetch_ohlcv = lambda s, tf, limit=300: trend(tf, 300, end_open=now - now % HORIZON_SECONDS[tf]
                                                         if tf != "1w" else MONDAY + ((now - MONDAY) // 604800) * 604800,
                                                         slope=0.4)
    candles = trend("1h", 300, end_open=end_open, slope=0.4)
    monkeypatch.setattr("app.screener.service.resolve_and_fetch",
                        lambda symbol, timeframe, limit=300, default_provider="binance": (provider, symbol, candles))
    mtf_service.clear_cache()
    row = service.scan_symbol("BTCUSDT", timeframe="1h", limit=300)
    assert row.mtf_matrix is not None
    assert row.mtf_matrix.horizon("1h").direction == row.pipeline.direction.value
    assert row.mtf_matrix.horizon("1h").bar_open == row.candles[-1].time


def test_factsheet_mtf_facts_carry_horizon_timeframe_and_absences():
    from app.agents.factsheet import facts_from_mtf

    m = _matrix({"1h": 0.5, "4h": -0.5, "1d": 0.5, "1w": None})
    facts = {f["id"]: f for f in facts_from_mtf({"mtf_matrix": m.to_dict()}, timeframe="1h")}
    assert facts["mtf.4h.direction"]["value"] == "SHORT" and facts["mtf.4h.direction"]["timeframe"] == "4h"
    assert facts["mtf.4h.direction"]["known_at"] == facts["mtf.4h.direction"]["as_of"] + 4 * 3600
    assert facts["mtf.1w.direction"]["status"] == "unavailable"
    assert facts["mtf.1w.direction"]["reason"] == "provider_no_timeframe"
    assert facts["mtf.1w.state"]["value"] == "UNAVAILABLE"
    assert facts["mtf.summary.opposed"]["display"] == "4h" and facts["mtf.summary.aligned"]["display"] == "1d"
    assert all(f["validation_status"] == "NON_VALIDE" for f in facts.values())
    missing = facts_from_mtf(None, timeframe="1h", reason="pipeline_error")
    assert missing[0]["status"] == "unavailable" and missing[0]["reason"] == "pipeline_error"
