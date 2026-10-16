"""V1-B — consolidated Python engine context for Eve modes.

Projects FactSheet + pipeline into a structured snapshot. The LLM must not
recompute indicators already present here.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any

from app.agents.factsheet import build_factsheet
from app.eve.actions import normalize_action

CONTEXT_SCHEMA = "ichivol.eve.context.v1"


def _iso_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_engine_context(
    symbol: str,
    timeframe: str = "1h",
    *,
    factsheet: dict[str, Any] | None = None,
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

    return {
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
    }
