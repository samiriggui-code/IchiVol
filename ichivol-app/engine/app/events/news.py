"""Symbol-scoped news candidates (causal: published_at ≤ as_of).

Wraps ``app.context.news.fetch_news`` — does not vote and never raises.
"""

from __future__ import annotations

import re
from typing import Sequence

from app.context.news import NewsItem, fetch_news
from app.events.classifier import classify_headline
from app.events.types import EventCategory, ExternalEventRef

# Common crypto aliases for symbol relevance (base asset → title tokens).
_ALIASES: dict[str, tuple[str, ...]] = {
    "BTC": ("bitcoin", "btc"),
    "ETH": ("ethereum", "eth", "ether"),
    "SOL": ("solana", "sol"),
    "XRP": ("xrp", "ripple"),
    "BNB": ("bnb", "binance coin"),
    "ADA": ("cardano", "ada"),
    "DOGE": ("dogecoin", "doge"),
    "AVAX": ("avalanche", "avax"),
    "DOT": ("polkadot", "dot"),
    "LINK": ("chainlink", "link"),
    "MATIC": ("polygon", "matic"),
    "ATOM": ("cosmos", "atom"),
    "LTC": ("litecoin", "ltc"),
    "UNI": ("uniswap", "uni"),
    "AAVE": ("aave",),
}


def symbol_base(symbol: str) -> str:
    """BTCUSDT / BTC-USD / BTCUSD → BTC."""
    s = symbol.upper().replace("-", "").replace("/", "").replace("_", "")
    for quote in ("USDT", "USDC", "BUSD", "USD", "EUR", "BTC", "ETH"):
        if s.endswith(quote) and len(s) > len(quote):
            return s[: -len(quote)]
    return s


def symbol_tokens(symbol: str) -> tuple[str, ...]:
    base = symbol_base(symbol)
    aliases = _ALIASES.get(base, ())
    # Always include the bare base ticker as a whole-word-ish token.
    return (base.lower(),) + tuple(a.lower() for a in aliases if a.lower() != base.lower())


def symbol_relevance(title: str, symbol: str) -> float:
    """0..1 — how clearly the headline mentions this symbol."""
    text = f" {title.lower()} "
    tokens = symbol_tokens(symbol)
    if not tokens:
        return 0.0
    hits = 0
    for tok in tokens:
        # Word-ish: avoid matching 'eth' inside 'something' via boundaries.
        if len(tok) <= 3:
            if re.search(rf"(?<![a-z0-9]){re.escape(tok)}(?![a-z0-9])", text):
                hits += 1
        elif tok in text:
            hits += 1
    if hits == 0:
        return 0.0
    # Primary ticker or known alias hit weighs more.
    base = symbol_base(symbol).upper()
    aliases = _ALIASES.get(base, ())
    text_l = title.lower()
    if re.search(rf"(?<![a-z0-9]){re.escape(base.lower())}(?![a-z0-9])", f" {text_l} ") or any(
        (a.lower() in text_l if len(a) > 3 else bool(re.search(rf"(?<![a-z0-9]){re.escape(a.lower())}(?![a-z0-9])", f" {text_l} ")))
        for a in aliases
    ):
        return min(1.0, 0.55 + 0.25 * hits)
    return min(1.0, 0.35 * hits)


def news_item_to_ref(
    item: NewsItem,
    *,
    symbol: str,
    bar_time: int,
) -> ExternalEventRef | None:
    """Map a feed item to a candidate; drop if no usable published_at or future."""
    if item.published_at is None:
        return None
    if item.published_at > bar_time:
        return None
    rel = symbol_relevance(item.title, symbol)
    if rel <= 0.0:
        return None
    category = classify_headline(item.title)
    # Crypto headlines without a clearer bucket stay CRYPTO_SPECIFIC when relevant.
    if category == EventCategory.UNKNOWN and rel >= 0.55:
        category = EventCategory.CRYPTO_SPECIFIC
    return ExternalEventRef(
        source="symbol_news",
        category=category,
        title=item.title,
        published_at=int(item.published_at),
        url=item.url,
        symbol_relevance=rel,
        temporal_proximity_s=max(0, bar_time - int(item.published_at)),
        match_confidence=0.0,  # filled by correlate
    )


def fetch_symbol_news(
    symbol: str,
    *,
    as_of: int,
    limit: int = 40,
    sources: list[str] | None = None,
    min_relevance: float = 0.35,
) -> list[ExternalEventRef]:
    """Causal symbol news: published_at ≤ as_of and title mentions symbol."""
    raw = fetch_news(limit=max(limit * 3, 60), sources=sources)
    out: list[ExternalEventRef] = []
    for item in raw:
        ref = news_item_to_ref(item, symbol=symbol, bar_time=as_of)
        if ref is None or ref.symbol_relevance < min_relevance:
            continue
        out.append(ref)
        if len(out) >= limit:
            break
    return out


def candidates_from_news_items(
    items: Sequence[NewsItem],
    *,
    symbol: str,
    as_of: int,
    min_relevance: float = 0.35,
) -> list[ExternalEventRef]:
    """Testable path: same filters without network."""
    out: list[ExternalEventRef] = []
    for item in items:
        ref = news_item_to_ref(item, symbol=symbol, bar_time=as_of)
        if ref is None or ref.symbol_relevance < min_relevance:
            continue
        out.append(ref)
    return out
