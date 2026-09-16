from __future__ import annotations

import httpx
import pytest

from app.context import news


@pytest.fixture(autouse=True)
def _clear_cache():
    news._cache.clear()
    yield
    news._cache.clear()


_SAMPLE_RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Sample Feed</title>
    <item>
      <title>Bitcoin breaks $100k</title>
      <link>https://example.com/btc-100k</link>
      <pubDate>Wed, 16 Sep 2026 12:00:00 GMT</pubDate>
    </item>
    <item>
      <title>Ethereum upgrade ships</title>
      <link>https://example.com/eth-upgrade</link>
      <pubDate>Wed, 16 Sep 2026 10:00:00 GMT</pubDate>
    </item>
  </channel>
</rss>
"""


class FakeResp:
    def __init__(self, text: str, ok: bool = True):
        self.text = text
        self._ok = ok

    def raise_for_status(self) -> None:
        if not self._ok:
            raise httpx.HTTPError("boom")


def test_fetch_news_parses_title_link_and_date(monkeypatch):
    monkeypatch.setattr(news.httpx, "get", lambda *a, **k: FakeResp(_SAMPLE_RSS))

    items = news.fetch_news(sources=["coindesk"])
    assert len(items) == 2
    assert items[0].title == "Bitcoin breaks $100k"
    assert items[0].url == "https://example.com/btc-100k"
    assert items[0].source == "coindesk"
    assert items[0].published_at is not None
    # Most-recent-first.
    assert items[0].published_at >= items[1].published_at


def test_fetch_news_limit_is_respected(monkeypatch):
    monkeypatch.setattr(news.httpx, "get", lambda *a, **k: FakeResp(_SAMPLE_RSS))
    items = news.fetch_news(limit=1, sources=["coindesk"])
    assert len(items) == 1


def test_one_feed_failing_never_empties_the_others(monkeypatch):
    def _fake_get(url, **kwargs):
        if "coindesk" in url:
            raise httpx.HTTPError("network down")
        return FakeResp(_SAMPLE_RSS)

    monkeypatch.setattr(news.httpx, "get", _fake_get)
    items = news.fetch_news(sources=["coindesk", "cointelegraph"])
    # coindesk failed -> empty, cointelegraph succeeded -> 2 items still returned.
    assert len(items) == 2
    assert all(i.source == "cointelegraph" for i in items)


def test_unparsable_xml_degrades_to_empty_list_not_a_crash(monkeypatch):
    monkeypatch.setattr(news.httpx, "get", lambda *a, **k: FakeResp("not xml at all <<<"))
    items = news.fetch_news(sources=["coindesk"])
    assert items == []


def test_unknown_source_name_is_silently_skipped(monkeypatch):
    monkeypatch.setattr(news.httpx, "get", lambda *a, **k: FakeResp(_SAMPLE_RSS))
    items = news.fetch_news(sources=["not_a_real_feed"])
    assert items == []


def test_result_is_cached_within_ttl(monkeypatch):
    calls = {"n": 0}

    def _fake_get(url, **kwargs):
        calls["n"] += 1
        return FakeResp(_SAMPLE_RSS)

    monkeypatch.setattr(news.httpx, "get", _fake_get)
    news.fetch_news(sources=["coindesk"])
    news.fetch_news(sources=["coindesk"])
    assert calls["n"] == 1  # second call served from cache
