"""Symbol news + classifier — causal filters, no network required."""

from __future__ import annotations

from app.context.news import NewsItem
from app.events.classifier import classify_headline
from app.events.news import candidates_from_news_items, symbol_relevance
from app.events.types import EventCategory


def test_classify_crypto_and_fed():
    assert classify_headline("Bitcoin ETF inflows hit record") == EventCategory.CRYPTO_SPECIFIC
    assert classify_headline("Fed signals rate cut next month") == EventCategory.CENTRAL_BANK
    assert classify_headline("SEC sues exchange over tokens") == EventCategory.REGULATORY
    assert classify_headline("Random lifestyle blog") == EventCategory.UNKNOWN


def test_symbol_relevance_btc():
    assert symbol_relevance("Bitcoin plunges amid ETF news", "BTCUSDT") >= 0.55
    assert symbol_relevance("Ethereum upgrade ships", "BTCUSDT") == 0.0
    assert symbol_relevance("SOL rallies on meme volume", "SOLUSDT") >= 0.55


def test_future_news_dropped():
    bar_time = 1_700_000_000
    items = [
        NewsItem(
            title="Bitcoin crashes after whale dump",
            url="https://example.com/a",
            source="coindesk",
            published_at=bar_time + 3600,  # future → must drop
        ),
        NewsItem(
            title="Bitcoin recovers from weekend dip",
            url="https://example.com/b",
            source="coindesk",
            published_at=bar_time - 1800,
        ),
        NewsItem(
            title="Ethereum gas fees spike",
            url="https://example.com/c",
            source="cointelegraph",
            published_at=bar_time - 100,
        ),
    ]
    refs = candidates_from_news_items(items, symbol="BTCUSDT", as_of=bar_time)
    assert len(refs) == 1
    assert refs[0].published_at == bar_time - 1800
    assert refs[0].source == "symbol_news"
    assert refs[0].symbol_relevance > 0


def test_missing_published_at_dropped():
    items = [
        NewsItem(
            title="Bitcoin mystery headline",
            url="https://example.com/x",
            source="coindesk",
            published_at=None,
        ),
    ]
    assert candidates_from_news_items(items, symbol="BTCUSDT", as_of=1_700_000_000) == []
