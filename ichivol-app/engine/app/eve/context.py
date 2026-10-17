"""V1-B — consolidated Python engine context for Eve modes.

Projects FactSheet + pipeline into a structured snapshot. The LLM must not
recompute indicators already present here.

Dense JEV snapshot (buberlo): numeric/compact state ≤ ~400 tokens for System One.
Full context stays available for modes / dossier; JEV calls use ``jev_state``.
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from typing import Any

from app.agents.factsheet import build_factsheet
from app.eve.actions import normalize_action
from app.eve.event_radar import radar_for_context

CONTEXT_SCHEMA = "ichivol.eve.context.v1"
DENSE_SCHEMA = "ichivol.eve.jev_state.v1"
# buberlo: STATE SNAPSHOT < 400 tokens (≈ chars/4 heuristic).
JEV_STATE_TOKEN_BUDGET = 400
_CHARS_PER_TOKEN = 4
_MAX_DENSE_FACTS = 24


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def estimate_tokens(payload: Any) -> int:
    """Rough token count for budget checks (compact JSON, no spaces)."""
    try:
        raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), default=str)
    except (TypeError, ValueError):
        raw = str(payload)
    return max(1, (len(raw) + _CHARS_PER_TOKEN - 1) // _CHARS_PER_TOKEN)


def _compact_value(value: Any) -> Any:
    if isinstance(value, float):
        return round(value, 6)
    if isinstance(value, (int, bool)) or value is None:
        return value
    if isinstance(value, str):
        return value[:48]
    if isinstance(value, (list, tuple)):
        return [_compact_value(v) for v in value[:4]]
    if isinstance(value, dict):
        return {str(k)[:24]: _compact_value(v) for k, v in list(value.items())[:6]}
    return str(value)[:48]


def _fact_priority(fact: dict[str, Any]) -> tuple[int, int]:
    role = str(fact.get("decision_role") or "").lower()
    role_rank = 0 if role in ("signal", "decision") else 1 if role == "context" else 2
    ok_rank = 0 if fact.get("status") == "ok" and fact.get("value") is not None else 1
    return (ok_rank, role_rank)


def dense_jev_state(
    context: dict[str, Any],
    *,
    token_budget: int = JEV_STATE_TOKEN_BUDGET,
) -> dict[str, Any]:
    """Build a dense PIT snapshot for JEV ``state`` (buberlo <400 tokens).

    Never invents values — only projects what is already in ``context``.
    """
    baseline = context.get("baseline") if isinstance(context.get("baseline"), dict) else {}
    radar = context.get("event_radar") if isinstance(context.get("event_radar"), dict) else {}
    facts = [f for f in (context.get("facts") or []) if isinstance(f, dict)]
    facts_sorted = sorted(facts, key=_fact_priority)

    f_map: dict[str, Any] = {}
    for fact in facts_sorted:
        if len(f_map) >= _MAX_DENSE_FACTS:
            break
        if fact.get("status") != "ok" or fact.get("value") is None:
            continue
        key = str(fact.get("field") or fact.get("id") or "").strip()
        if not key:
            continue
        # Prefer short field names; strip engine prefix noise when redundant.
        if key.startswith("pipeline.") and key != "pipeline.decision":
            continue
        f_map[key[:40]] = _compact_value(fact.get("value"))

    state: dict[str, Any] = {
        "schema": DENSE_SCHEMA,
        "sym": context.get("symbol"),
        "tf": context.get("timeframe"),
        "as_of": context.get("as_of") or context.get("known_at"),
        "dq": _compact_value(context.get("data_quality")),
        "base": baseline.get("action_mapped") or baseline.get("decision"),
        "base_c": _compact_value(baseline.get("confidence")),
        "f": f_map,
        "unavail_n": len(context.get("unavailable") or []),
        "fact_ok": context.get("fact_ok_count"),
        "fact_n": context.get("fact_count"),
    }
    if radar.get("enabled"):
        state["radar"] = {
            "dir": radar.get("direction"),
            "imp": radar.get("impact"),
            "rel": radar.get("relevance"),
            "fr": radar.get("freshness"),
            "c": _compact_value(radar.get("confidence")),
            "n": radar.get("event_count"),
        }
    elif radar:
        state["radar"] = {"on": False}

    # Shrink facts until under budget (drop lowest-priority keys last-in-first-out).
    tokens = estimate_tokens(state)
    while tokens > token_budget and state["f"]:
        drop_key = next(reversed(state["f"]))
        del state["f"][drop_key]
        tokens = estimate_tokens(state)

    state["tok"] = tokens
    state["tok_budget"] = token_budget
    return state


def jev_state_for(context: dict[str, Any], **extra: Any) -> dict[str, Any]:
    """Dense snapshot for System One, with optional mode extras under budget."""
    base = context.get("jev_state")
    if not isinstance(base, dict):
        base = dense_jev_state(context)
    if not extra:
        return base
    out = dict(base)
    budget = int(out.get("tok_budget") or JEV_STATE_TOKEN_BUDGET)
    for key, value in extra.items():
        if value is None:
            continue
        out[str(key)[:24]] = _compact_value(value)
    tokens = estimate_tokens(out)
    # Drop fact keys first if extras push over budget.
    while tokens > budget and isinstance(out.get("f"), dict) and out["f"]:
        drop_key = next(reversed(out["f"]))
        del out["f"][drop_key]
        tokens = estimate_tokens(out)
    out["tok"] = tokens
    out["tok_budget"] = budget
    return out


def build_engine_context(
    symbol: str,
    timeframe: str = "1h",
    *,
    factsheet: dict[str, Any] | None = None,
    include_event_radar: bool = True,
    event_radar_use_jev: bool = True,
) -> dict[str, Any]:
    """Build a structured context. Never invents missing engine values."""
    sym = symbol.strip().upper()
    tf = (timeframe or "1h").strip() or "1h"
    generated_at = _iso_now()
    known_at = int(time.time())

    fs = factsheet if isinstance(factsheet, dict) else None
    error: str | None = None
    if fs is None:
        try:
            fs = build_factsheet(sym, tf)
        except Exception as exc:  # noqa: BLE001 — surface as context error
            error = type(exc).__name__
            fs = {
                "schema": "ichivol.factsheet.v1",
                "symbol": sym,
                "timeframe": tf,
                "facts": [],
                "factsheet_id": None,
            }

    facts = [f for f in (fs.get("facts") or []) if isinstance(f, dict)]
    engines: dict[str, list[dict[str, Any]]] = {}
    unavailable: list[str] = []
    ok_count = 0
    for fact in facts:
        eng = str(fact.get("engine") or "unknown")
        item = {
            "id": fact.get("id"),
            "field": fact.get("field"),
            "value": fact.get("value"),
            "display": fact.get("display"),
            "unit": fact.get("unit"),
            "timeframe": fact.get("timeframe") or tf,
            "as_of": fact.get("as_of"),
            "known_at": fact.get("known_at") or known_at,
            "source": fact.get("source"),
            "status": fact.get("status"),
            "reason": fact.get("reason"),
            "decision_role": fact.get("decision_role"),
        }
        engines.setdefault(eng, []).append(item)
        if fact.get("status") == "ok" and fact.get("value") is not None:
            ok_count += 1
        else:
            unavailable.append(str(fact.get("id") or fact.get("field") or eng))

    baseline_decision = None
    baseline_confidence = None
    pipeline = None
    for fact in facts:
        fid = str(fact.get("id") or "")
        field = str(fact.get("field") or "")
        if field in ("decision", "pipeline.decision") or fid.endswith(".decision"):
            if baseline_decision is None and fact.get("value") is not None:
                baseline_decision = str(fact.get("value"))
        if "confidence" in field and baseline_confidence is None and isinstance(fact.get("value"), (int, float)):
            baseline_confidence = float(fact["value"])
        if field == "pipeline" and isinstance(fact.get("value"), dict):
            pipeline = fact["value"]

    total = max(len(facts), 1)
    data_quality = round(ok_count / total, 4) if facts else 0.0

    event_radar: dict[str, Any] | None = None
    if include_event_radar:
        try:
            event_radar = radar_for_context(
                sym, as_of=known_at, use_jev=event_radar_use_jev
            )
        except Exception:  # noqa: BLE001 — context must stay fail-soft
            event_radar = {
                "enabled": False,
                "error": "event_radar_failed",
                "reference_only": True,
            }

    ctx: dict[str, Any] = {
        "schema": CONTEXT_SCHEMA,
        "symbol": sym,
        "timeframe": tf,
        "generated_at": generated_at,
        "known_at": known_at,
        "as_of": fs.get("as_of"),
        "factsheet_id": fs.get("factsheet_id"),
        "factsheet_schema": fs.get("schema"),
        "baseline": {
            "decision": baseline_decision,
            "action_mapped": normalize_action(baseline_decision),
            "confidence": baseline_confidence,
            "pipeline": pipeline,
        },
        "engines": engines,
        "facts": facts,
        "unavailable": unavailable[:50],
        "data_quality": data_quality,
        "fact_count": len(facts),
        "fact_ok_count": ok_count,
        "error": error,
        "source": "python_engines+factsheet",
        "event_radar": event_radar,
    }
    ctx["jev_state"] = dense_jev_state(ctx)
    return ctx
