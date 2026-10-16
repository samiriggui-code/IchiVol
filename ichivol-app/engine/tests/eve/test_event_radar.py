"""Event Radar — instrument-scoped, JEV-first, rules fallback (no OpenRouter)."""

from __future__ import annotations

from types import SimpleNamespace

from app.eve.event_radar import analyze_symbol, collect_instrument_events, radar_for_context


def _ref(title: str, *, rel: float = 0.8, published_at: int = 1_700_000_000):
    return SimpleNamespace(
        title=title,
        url="https://example.test/x",
        source="symbol_news",
        published_at=published_at,
        symbol_relevance=rel,
        category=SimpleNamespace(value="crypto_specific"),
    )


def test_disabled_returns_flag(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.eve.event_radar.resolved_values",
        lambda: {
            "EVENT_RADAR_ENABLED": False,
            "EVENT_RADAR_JEV_MIN_CONFIDENCE": 0.65,
            "EVENT_RADAR_NEWS_LOOKBACK_DAYS": 2,
            "EVENT_RADAR_MAX_EVENTS": 8,
            "EVENT_RADAR_CRYPTO_RSS_ENABLED": True,
            "EVENT_RADAR_YAHOO_FINANCE_RSS_ENABLED": True,
            "EVENT_RADAR_SEC_EDGAR_ENABLED": False,
        },
    )
    out = analyze_symbol("BTCUSDT", use_jev=False)
    assert out["enabled"] is False
    assert out["reason"] == "event_radar_disabled"


def test_rules_fallback_when_jev_rejects(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("EVE_SETTINGS_OVERRIDES_PATH", str(tmp_path / "o.json"))
    from app.eve import settings_schema as ss

    ss.apply_patch({"EVENT_RADAR_ENABLED": True})

    def fake_news(symbol, **kwargs):
        return [
            _ref(
                "Bitcoin ETF inflows surge",
                published_at=int(kwargs.get("as_of", 1_700_000_100)),
            )
        ]

    def fake_jev(state, questions, **kwargs):
        return {"ok": False, "error": "timeout", "late": True}

    out = analyze_symbol(
        "BTCUSDT",
        as_of=1_700_000_100,
        use_jev=True,
        news_fetcher=fake_news,
        evaluate=fake_jev,
    )
    assert out["enabled"] is True
    assert out["provider"] == "rules"
    assert out["direction"] == "neutral"
    assert out["event_count"] == 1
    assert "jev" in (out.get("fallback_reason") or "")


def test_jev_success_path(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("EVE_SETTINGS_OVERRIDES_PATH", str(tmp_path / "o.json"))
    from app.eve import settings_schema as ss

    ss.apply_patch({"EVENT_RADAR_ENABLED": True, "EVENT_RADAR_JEV_MIN_CONFIDENCE": 0.5})

    def fake_news(symbol, **kwargs):
        return [_ref("ETH upgrade activates", rel=0.9, published_at=int(kwargs["as_of"]))]

    def fake_jev(state, questions, **kwargs):
        return {
            "ok": True,
            "request_model": "jev-test",
            "response_model": "jev-test",
            "latency_ms": 12,
            "answers": {
                "relevance": {"choice": "high", "confidence": 0.8},
                "direction": {"choice": "bullish", "confidence": 0.7},
                "impact": {"choice": "medium", "confidence": 0.6},
                "freshness": {"choice": "fresh", "confidence": 0.9},
            },
        }

    out = analyze_symbol(
        "ETHUSDT",
        as_of=1_700_000_200,
        news_fetcher=fake_news,
        evaluate=fake_jev,
    )
    assert out["provider"] == "jev"
    assert out["direction"] == "bullish"
    assert out["relevance"] == "high"
    assert out["confidence"] == 0.6


def test_lookback_filters_old_events() -> None:
    now = 1_700_100_000
    old = now - 3 * 86400

    def fake_news(symbol, **kwargs):
        return [
            _ref("old", published_at=old),
            _ref("fresh BTC news", published_at=now - 3600),
        ]

    events, status = collect_instrument_events(
        "BTCUSDT",
        as_of=now,
        settings={
            "enabled": True,
            "news_lookback_days": 1,
            "max_events": 8,
            "crypto_rss_enabled": True,
            "sec_edgar_enabled": False,
            "jev_min_confidence": 0.65,
            "yahoo_finance_rss_enabled": False,
        },
        news_fetcher=fake_news,
    )
    assert len(events) == 1
    assert "fresh" in events[0]["title"]
    assert status["crypto_rss"] == "ok"


def test_radar_for_context_compact(monkeypatch) -> None:
    monkeypatch.setattr(
        "app.eve.event_radar.resolved_values",
        lambda: {
            "EVENT_RADAR_ENABLED": False,
            "EVENT_RADAR_JEV_MIN_CONFIDENCE": 0.65,
            "EVENT_RADAR_NEWS_LOOKBACK_DAYS": 2,
            "EVENT_RADAR_MAX_EVENTS": 8,
            "EVENT_RADAR_CRYPTO_RSS_ENABLED": True,
            "EVENT_RADAR_YAHOO_FINANCE_RSS_ENABLED": True,
            "EVENT_RADAR_SEC_EDGAR_ENABLED": False,
        },
    )
    compact = radar_for_context("BTCUSDT", use_jev=False)
    assert compact is not None
    assert compact["enabled"] is False
