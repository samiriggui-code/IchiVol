"""Event Radar — instrument-scoped news → JEV CHOICE (QuantDinger P1).

Reference-only: enriches Eve context, never opens risk.
Fallback when JEV down = deterministic rules (never OpenRouter as System One).
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any, Callable

from app.eve.settings_schema import resolved_values
from app.events.news import fetch_symbol_news, symbol_base
from app.jev.adapter import evaluate as jev_evaluate

PIPELINE_VERSION = "ichivol.event_radar.v1"

JEV_QUESTIONS: dict[str, Any] = {
    "relevance": {
        "type": "choice",
        "instructions": (
            "Assess whether the supplied current events are materially relevant "
            "to the requested instrument."
        ),
        "criteria": {
            "high": "Several fresh events have a direct and credible connection.",
            "medium": "At least one event is relevant, but evidence is indirect.",
            "low": "Little credible connection to the instrument.",
        },
    },
    "direction": {
        "type": "choice",
        "instructions": (
            "Estimate the near-term directional effect of the supplied events "
            "on the instrument."
        ),
        "criteria": {
            "bullish": "Evidence more likely supports price appreciation.",
            "bearish": "Evidence more likely supports price depreciation.",
            "neutral": "No material directional effect.",
            "mixed": "Material bullish and bearish effects coexist.",
        },
    },
    "impact": {
        "type": "choice",
        "instructions": (
            "Estimate the likely market impact of these events over the next "
            "trading session."
        ),
        "criteria": {
            "high": "Can plausibly produce a large or abrupt price response.",
            "medium": "May cause a visible but ordinary price response.",
            "low": "Unlikely to move the instrument materially.",
        },
    },
    "freshness": {
        "type": "choice",
        "instructions": "Assess whether the evidence is current enough now.",
        "criteria": {
            "fresh": "Most evidence is current and timely.",
            "mixed": "Both current and older items.",
            "stale": "Most evidence is too old.",
        },
    },
}

JEV_OPTIONS: dict[str, set[str]] = {
    "relevance": {"high", "medium", "low"},
    "direction": {"bullish", "bearish", "neutral", "mixed"},
    "impact": {"high", "medium", "low"},
    "freshness": {"fresh", "mixed", "stale"},
}


def _radar_settings() -> dict[str, Any]:
    v = resolved_values()
    return {
        "enabled": bool(v.get("EVENT_RADAR_ENABLED")),
        "jev_min_confidence": float(v.get("EVENT_RADAR_JEV_MIN_CONFIDENCE") or 0.65),
        "news_lookback_days": max(1, int(v.get("EVENT_RADAR_NEWS_LOOKBACK_DAYS") or 2)),
        "max_events": max(1, min(20, int(v.get("EVENT_RADAR_MAX_EVENTS") or 8))),
        "crypto_rss_enabled": bool(v.get("EVENT_RADAR_CRYPTO_RSS_ENABLED", True)),
        "yahoo_finance_rss_enabled": bool(v.get("EVENT_RADAR_YAHOO_FINANCE_RSS_ENABLED", True)),
        "sec_edgar_enabled": bool(v.get("EVENT_RADAR_SEC_EDGAR_ENABLED", False)),
    }


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _choice_from_answers(answers: Any, key: str) -> tuple[str, float] | None:
    if not isinstance(answers, dict):
        return None
    raw = answers.get(key)
    if not isinstance(raw, dict):
        return None
    choice = str(raw.get("choice") or raw.get("selected") or "").strip().lower()
    if choice not in JEV_OPTIONS.get(key, set()):
        return None
    conf = raw.get("confidence")
    try:
        confidence = float(conf) if conf is not None else 0.0
    except (TypeError, ValueError):
        confidence = 0.0
    return choice, min(max(confidence, 0.0), 1.0)


def _rules_analyze(events: list[dict[str, Any]], *, as_of: int) -> dict[str, Any]:
    """Deterministic fallback — observation only, never invents a trade bias."""
    if not events:
        return {
            "direction": "neutral",
            "confidence": 0.0,
            "impact": "low",
            "relevance": "low",
            "freshness": "fresh",
            "summary": "No instrument-scoped events in lookback.",
            "provider": "rules",
            "model": "rules-v1",
        }
    mean_rel = sum(float(e.get("symbol_relevance") or 0) for e in events) / len(events)
    if mean_rel >= 0.7:
        relevance = "high"
    elif mean_rel >= 0.4:
        relevance = "medium"
    else:
        relevance = "low"
    ages = [max(0, as_of - int(e.get("published_at") or as_of)) for e in events]
    mean_age_h = (sum(ages) / len(ages)) / 3600.0 if ages else 0.0
    if mean_age_h <= 12:
        freshness = "fresh"
    elif mean_age_h <= 48:
        freshness = "mixed"
    else:
        freshness = "stale"
    if len(events) >= 5 and mean_rel >= 0.55:
        impact = "medium"
    else:
        impact = "low"
    return {
        "direction": "neutral",
        "confidence": round(min(0.55, mean_rel), 4),
        "impact": impact,
        "relevance": relevance,
        "freshness": freshness,
        "summary": f"{len(events)} event(s); rules fallback (no JEV directional call).",
        "provider": "rules",
        "model": "rules-v1",
    }


def _analyze_jev(
    symbol: str,
    events: list[dict[str, Any]],
    *,
    min_confidence: float,
    evaluate: Callable[..., dict[str, Any]] = jev_evaluate,
) -> dict[str, Any] | None:
    envelope = evaluate(
        {"symbol": symbol, "events": events, "reference_only": True},
        JEV_QUESTIONS,
    )
    if not envelope.get("ok"):
        return None
    answers = envelope.get("answers") or {}
    resolved: dict[str, tuple[str, float]] = {}
    for name in JEV_OPTIONS:
        parsed = _choice_from_answers(answers, name)
        if parsed is None:
            return None
        choice, conf = parsed
        if conf < min_confidence:
            return None
        resolved[name] = (choice, conf)
    confidence = min(v[1] for v in resolved.values())
    return {
        "direction": resolved["direction"][0],
        "confidence": confidence,
        "impact": resolved["impact"][0],
        "relevance": resolved["relevance"][0],
        "freshness": resolved["freshness"][0],
        "summary": "",
        "provider": "jev",
        "model": envelope.get("response_model") or envelope.get("request_model"),
        "jev_latency_ms": envelope.get("latency_ms"),
    }


def collect_instrument_events(
    symbol: str,
    *,
    as_of: int | None = None,
    settings: dict[str, Any] | None = None,
    news_fetcher: Callable[..., list] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    cfg = settings or _radar_settings()
    now = int(as_of if as_of is not None else time.time())
    lookback = int(cfg["news_lookback_days"]) * 86400
    max_events = int(cfg["max_events"])
    source_status: dict[str, Any] = {
        "pipeline_version": PIPELINE_VERSION,
        "crypto_rss": "off",
        "yahoo_finance_rss": "not_wired",
        "sec_edgar": "not_wired" if not cfg["sec_edgar_enabled"] else "flag_on_no_provider",
    }
    events: list[dict[str, Any]] = []
    if not cfg["crypto_rss_enabled"]:
        source_status["crypto_rss"] = "disabled"
        return events, source_status

    fetcher = news_fetcher or fetch_symbol_news
    try:
        refs = fetcher(
            symbol,
            as_of=now,
            limit=max_events * 3,
            sources=["coindesk", "cointelegraph"],
            min_relevance=0.35,
        )
        source_status["crypto_rss"] = "ok"
    except Exception as exc:  # noqa: BLE001 — fail-soft
        source_status["crypto_rss"] = f"error:{type(exc).__name__}"
        refs = []

    cutoff = now - lookback
    for ref in refs:
        pub = int(getattr(ref, "published_at", 0) or 0)
        if pub < cutoff:
            continue
        events.append(
            {
                "title": getattr(ref, "title", ""),
                "url": getattr(ref, "url", None),
                "source": getattr(ref, "source", "symbol_news"),
                "published_at": pub,
                "symbol_relevance": float(getattr(ref, "symbol_relevance", 0) or 0),
                "category": getattr(getattr(ref, "category", None), "value", None)
                or str(getattr(ref, "category", "") or ""),
            }
        )
        if len(events) >= max_events:
            break
    return events, source_status


def analyze_symbol(
    symbol: str,
    *,
    as_of: int | None = None,
    use_jev: bool = True,
    settings: dict[str, Any] | None = None,
    news_fetcher: Callable[..., list] | None = None,
    evaluate: Callable[..., dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Run Event Radar for one instrument. Never authorizes risk."""
    started = time.perf_counter()
    cfg = settings or _radar_settings()
    sym = symbol.strip().upper()
    now = int(as_of if as_of is not None else time.time())

    if not cfg["enabled"]:
        return {
            "schema": PIPELINE_VERSION,
            "enabled": False,
            "symbol": sym,
            "base": symbol_base(sym),
            "reference_only": True,
            "reason": "event_radar_disabled",
            "events": [],
            "created_at": _iso_now(),
        }

    events, source_status = collect_instrument_events(
        sym, as_of=now, settings=cfg, news_fetcher=news_fetcher
    )
    failures: list[str] = []
    result: dict[str, Any] | None = None

    if not events:
        failures.append("evidence:no_relevant_events")
        result = _rules_analyze([], as_of=now)
    elif use_jev:
        try:
            result = _analyze_jev(
                sym,
                events,
                min_confidence=float(cfg["jev_min_confidence"]),
                evaluate=evaluate or jev_evaluate,
            )
            if result is None:
                failures.append("jev:rejected_or_unavailable")
        except Exception as exc:  # noqa: BLE001
            failures.append(f"jev:{type(exc).__name__}")
            result = None

    if result is None:
        result = _rules_analyze(events, as_of=now)
        failures.append("fallback:rules")

    return {
        "schema": PIPELINE_VERSION,
        "enabled": True,
        "symbol": sym,
        "base": symbol_base(sym),
        "reference_only": True,
        "direction": result["direction"],
        "confidence": result["confidence"],
        "impact": result["impact"],
        "relevance": result["relevance"],
        "freshness": result["freshness"],
        "summary": result.get("summary") or "",
        "provider": result["provider"],
        "model": result.get("model") or "",
        "fallback_reason": "; ".join(failures),
        "source_status": source_status,
        "events": events,
        "event_count": len(events),
        "latency_ms": max(0, int((time.perf_counter() - started) * 1000)),
        "created_at": _iso_now(),
        "settings": {
            "lookback_days": cfg["news_lookback_days"],
            "max_events": cfg["max_events"],
            "jev_min_confidence": cfg["jev_min_confidence"],
        },
    }


def radar_for_context(
    symbol: str,
    *,
    as_of: int | None = None,
    use_jev: bool = True,
) -> dict[str, Any] | None:
    """Compact payload for ``build_engine_context`` — None when disabled."""
    cfg = _radar_settings()
    if not cfg["enabled"]:
        return {
            "enabled": False,
            "schema": PIPELINE_VERSION,
            "note": "EVENT_RADAR_ENABLED=false",
        }
    full = analyze_symbol(symbol, as_of=as_of, use_jev=use_jev, settings=cfg)
    return {
        "enabled": True,
        "schema": PIPELINE_VERSION,
        "direction": full.get("direction"),
        "confidence": full.get("confidence"),
        "impact": full.get("impact"),
        "relevance": full.get("relevance"),
        "freshness": full.get("freshness"),
        "provider": full.get("provider"),
        "event_count": full.get("event_count"),
        "summary": full.get("summary"),
        "fallback_reason": full.get("fallback_reason"),
        "reference_only": True,
        "events": [
            {
                "title": e.get("title"),
                "source": e.get("source"),
                "published_at": e.get("published_at"),
                "symbol_relevance": e.get("symbol_relevance"),
            }
            for e in (full.get("events") or [])[:5]
        ],
    }
