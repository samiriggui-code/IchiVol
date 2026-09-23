"""Heuristic headline → EventCategory (tone/taxonomy only — never BUY/SELL)."""

from __future__ import annotations

import re

from app.events.types import EventCategory

# Ordered: first match wins (more specific before UNKNOWN).
_RULES: tuple[tuple[EventCategory, tuple[str, ...]], ...] = (
    (
        EventCategory.CENTRAL_BANK,
        ("fed ", "fomc", "ecb", "boj", "rate hike", "rate cut", "interest rate", "powell"),
    ),
    (
        EventCategory.ECONOMIC_DATA,
        ("cpi", "inflation", "payroll", "nfp", "gdp", "pce", "unemployment", "jobs report"),
    ),
    (
        EventCategory.REGULATORY,
        ("sec ", "cftc", "regulation", "regulatory", "ban ", "lawsuit sec", "etf approval"),
    ),
    (
        EventCategory.LEGAL,
        ("lawsuit", "sued", "indictment", "court ", "settlement"),
    ),
    (
        EventCategory.EARNINGS,
        ("earnings", "quarterly results", "q1 ", "q2 ", "q3 ", "q4 ", "eps "),
    ),
    (
        EventCategory.GUIDANCE,
        ("guidance", "outlook", "raises forecast", "cuts forecast"),
    ),
    (
        EventCategory.M_AND_A,
        ("acquisition", "acquire", "merger", "takeover", "buyout"),
    ),
    (
        EventCategory.MANAGEMENT,
        ("ceo ", "cfo ", "resign", "appointed", "executive"),
    ),
    (
        EventCategory.ANALYST_RATING,
        ("upgrade", "downgrade", "price target", "initiates coverage"),
    ),
    (
        EventCategory.GEOPOLITICAL,
        ("war ", "sanction", "geopolit", "invasion", "conflict"),
    ),
    (
        EventCategory.CRYPTO_SPECIFIC,
        (
            "bitcoin",
            "btc",
            "ethereum",
            "eth ",
            "crypto",
            "blockchain",
            "defi",
            "stablecoin",
            "halving",
            "mining",
            "binance",
            "coinbase",
            "solana",
            "xrp",
        ),
    ),
    (
        EventCategory.MACRO_EVENT,
        ("macro", "market crash", "risk-off", "risk on"),
    ),
    (
        EventCategory.PRODUCT,
        ("launch", "mainnet", "upgrade", "hard fork", "protocol"),
    ),
)


def classify_headline(title: str) -> EventCategory:
    """Best-effort taxonomy from keywords. Never returns a trade direction."""
    text = f" {title.lower()} "
    text = re.sub(r"\s+", " ", text)
    for category, needles in _RULES:
        for needle in needles:
            if needle in text:
                return category
    return EventCategory.UNKNOWN
