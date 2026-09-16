"""Read-only crypto news adapter (CDC 2026-09-16, backlog item tagged
"Claude : adapters context (news / calendrier) opt-in, sans toucher
Ichimoku x RVOL"). Free, keyless RSS feeds -- same "gratuit, sans clé"
convention already used for biquote/CoinGecko
(docs/MARKET-DATA-STRATEGY.md). Pure context: `app/decision/pipeline.py`
never imports this module, and nothing here ever votes a direction or
changes a stage's status -- headlines are for a human (or Copilot's
evidence pack, later) to read, never for the engine to act on.

Best-effort by construction: one feed failing (network error, changed
markup) never blocks the others and never raises -- same "one bad source
never sinks the batch" convention used elsewhere (app/screener/service.py's
per-symbol OI/funding/MTF try/except, app/api/routes.py's batch endpoints).
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from email.utils import parsedate_to_datetime
from xml.etree import ElementTree

import httpx

FEEDS: dict[str, str] = {
    "coindesk": "https://www.coindesk.com/arc/outboundfeeds/rss/",
    "cointelegraph": "https://cointelegraph.com/rss",
}

_CACHE_TTL_SEC = 120.0
_cache: dict[str, tuple[float, list["NewsItem"]]] = {}
_lock = threading.Lock()


@dataclass(frozen=True)
class NewsItem:
    title: str
    url: str
    source: str
    published_at: int | None  # unix seconds; None when the feed's date didn't parse


def _parse_feed(source: str, xml_text: str) -> list[NewsItem]:
    try:
        root = ElementTree.fromstring(xml_text)
    except ElementTree.ParseError:
        return []

    items: list[NewsItem] = []
    for item in root.iter("item"):
        title_el = item.find("title")
        link_el = item.find("link")
        if title_el is None or link_el is None or not title_el.text or not link_el.text:
            continue

        published_at: int | None = None
        pub_el = item.find("pubDate")
        if pub_el is not None and pub_el.text:
            try:
                published_at = int(parsedate_to_datetime(pub_el.text).timestamp())
            except (TypeError, ValueError):
                published_at = None

        items.append(
            NewsItem(
                title=title_el.text.strip(),
                url=link_el.text.strip(),
                source=source,
                published_at=published_at,
            )
        )
    return items


def _fetch_one(source: str, url: str) -> list[NewsItem]:
    with _lock:
        hit = _cache.get(source)
        if hit is not None and time.monotonic() - hit[0] < _CACHE_TTL_SEC:
            return hit[1]

    try:
        response = httpx.get(url, timeout=10.0, headers={"User-Agent": "IchiVol/1.0 (context-adapter)"})
        response.raise_for_status()
        items = _parse_feed(source, response.text)
    except httpx.HTTPError:
        items = []

    with _lock:
        _cache[source] = (time.monotonic(), items)
    return items


def fetch_news(limit: int = 20, sources: list[str] | None = None) -> list[NewsItem]:
    """Most-recent-first, merged across `sources` (default: all of FEEDS).
    An unknown source name is silently skipped -- never raises."""
    wanted = sources if sources is not None else list(FEEDS.keys())
    all_items: list[NewsItem] = []
    for name in wanted:
        url = FEEDS.get(name)
        if url is None:
            continue
        all_items.extend(_fetch_one(name, url))

    all_items.sort(key=lambda i: i.published_at or 0, reverse=True)
    return all_items[:limit]
