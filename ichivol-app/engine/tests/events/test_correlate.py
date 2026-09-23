"""correlate_events — EVENT_MARKET only with causal match; anti-lookahead."""

from __future__ import annotations

from app.events.correlate import correlate_events, score_match
from app.events.types import (
    AnomalyType,
    EventCategory,
    ExternalEventRef,
    MarketAnomalyObservation,
    MarketRegime,
)


def _anomaly(
    *,
    suspected: bool = True,
    bar_time: int = 1_700_000_000,
    regime: MarketRegime = MarketRegime.UNKNOWN_EVENT,
) -> MarketAnomalyObservation:
    return MarketAnomalyObservation(
        symbol="BTCUSDT",
        timeframe="1h",
        bar_time=bar_time,
        event_suspected=suspected,
        event_type=AnomalyType.PRICE_SHOCK if suspected else AnomalyType.NONE,
        market_regime=regime if suspected else MarketRegime.NORMAL_MARKET,
        return_zscore=3.0 if suspected else 0.1,
        volume_zscore=2.0 if suspected else 0.1,
        range_atr_ratio=None,
        gap_atr_ratio=None,
        rvol=4.0 if suspected else 1.0,
        volatility_zscore=None,
        confidence=0.8 if suspected else 0.0,
        feature_version="event_anomaly_v0_placeholder",
        reasons=("test",),
    )


def _news(
    *,
    published_at: int,
    title: str = "Bitcoin ETF sees record inflows",
    relevance: float = 0.8,
) -> ExternalEventRef:
    return ExternalEventRef(
        source="symbol_news",
        category=EventCategory.CRYPTO_SPECIFIC,
        title=title,
        published_at=published_at,
        url="https://example.com/n",
        symbol_relevance=relevance,
    )


def test_future_candidate_rejected():
    anomaly = _anomaly(bar_time=1_700_000_000)
    future = _news(published_at=anomaly.bar_time + 60)
    assert score_match(anomaly, future) is None
    bundle = correlate_events(anomaly, [future])
    assert bundle.matches == ()
    assert bundle.market_regime == MarketRegime.UNKNOWN_EVENT


def test_match_promotes_event_market():
    anomaly = _anomaly(bar_time=1_700_000_000)
    past = _news(published_at=anomaly.bar_time - 3600, relevance=0.9)
    bundle = correlate_events(anomaly, [past], min_match_confidence=0.45)
    assert bundle.market_regime == MarketRegime.EVENT_MARKET
    assert bundle.anomaly.market_regime == MarketRegime.EVENT_MARKET
    assert len(bundle.matches) == 1
    assert bundle.matches[0].match_confidence >= 0.45
    assert bundle.matches[0].relation == "CORRELATED_EVENT"
    assert "signal" not in bundle.disclaimer.lower() or "n'est pas un signal" in bundle.disclaimer


def test_weak_relevance_stays_unknown():
    anomaly = _anomaly()
    weak = _news(published_at=anomaly.bar_time - 100, relevance=0.1)
    bundle = correlate_events(anomaly, [weak], min_match_confidence=0.45)
    assert bundle.market_regime == MarketRegime.UNKNOWN_EVENT
    # May still list weak matches below threshold or drop after score — either OK
    # as long as regime is not EVENT_MARKET.
    assert all(m.match_confidence < 0.45 for m in bundle.matches) or bundle.matches == ()


def test_no_anomaly_stays_normal_even_with_news():
    anomaly = _anomaly(suspected=False, regime=MarketRegime.NORMAL_MARKET)
    past = _news(published_at=anomaly.bar_time - 60, relevance=0.95)
    bundle = correlate_events(anomaly, [past])
    assert bundle.market_regime == MarketRegime.NORMAL_MARKET


def test_out_of_lag_window_ignored():
    anomaly = _anomaly(bar_time=1_700_000_000)
    old = _news(published_at=anomaly.bar_time - (10 * 86400), relevance=0.95)
    bundle = correlate_events(anomaly, [old], max_lag_s=48 * 3600)
    assert bundle.matches == ()
    assert bundle.market_regime == MarketRegime.UNKNOWN_EVENT
