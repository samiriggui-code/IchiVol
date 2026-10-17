"""The state Ève sends to JEV: every calculation the engine made for one (symbol, timeframe) closed bar.

Built from the screener row already computed this cycle (``detail_dict``: pipeline stages, Ichimoku, RVOL,
ATR stop, context, evidence, CHoCH / FVG / Fibonacci lab context, MTF matrix, anomalies, data quality) plus
the portfolio's own position. No new market-data call. JEV never sees anything the engine did not compute.
"""

from __future__ import annotations

import json
from typing import Any

MAX_LIST_ITEMS = 12
MAX_STR = 400
# ~13k chars ≈ 7k tokens: fits jevos-v4 (8192-token context) with the questions; the same state goes to every
# source so hosted JEV and jevos are compared on identical inputs.
MAX_STATE_CHARS = 13_000

# Audit-only blocks with no market information.
_DROP_KEYS = {"data_provenance", "weights_used", "strategy_version", "volume_type", "disclaimer", "feature_version"}


# Never trimmed: the staged decision and the indicators it was built from.
_CORE_KEYS = {"symbol", "timeframe", "price", "timestamp", "decision", "direction", "pipeline", "ichimoku",
              "ichimoku_score", "rvol", "rvol_detail", "risk", "signal_timing", "confidence", "probability"}


def _compact(value: Any, depth: int = 0) -> Any:
    if isinstance(value, float):
        if value != value:
            return None
        return float(f"{value:.6g}")
    if isinstance(value, str):
        return value if len(value) <= MAX_STR else value[: MAX_STR - 1] + "…"
    if isinstance(value, dict):
        return {
            str(k): _compact(v, depth + 1)
            for k, v in value.items()
            if k not in _DROP_KEYS and v is not None and v != [] and v != {}
        }
    if isinstance(value, (list, tuple)):
        items = [_compact(v, depth + 1) for v in list(value)[:MAX_LIST_ITEMS]]
        return items
    return value


def engine_calculations(detail: dict[str, Any]) -> dict[str, Any]:
    """Every engine block of a decision detail, compacted."""
    return _compact(detail)


def build_state(
    detail: dict[str, Any],
    *,
    position: dict[str, Any] | None,
    allow_short: bool,
    portfolio_code: str,
) -> dict[str, Any]:
    calcs = engine_calculations(detail)
    state: dict[str, Any] = {
        "task": "Decide the trade for this market from the IchiVol engine calculations below.",
        "instrument": {"symbol": detail.get("symbol"), "timeframe": detail.get("timeframe"),
                       "price": detail.get("price"), "bar_open_time": detail.get("timestamp")},
        "portfolio": {"code": portfolio_code, "short_selling_allowed": allow_short,
                      "position": position or "flat"},
        "engine": calcs,
    }
    text = json.dumps(state, ensure_ascii=False, default=str)
    if len(text) > MAX_STATE_CHARS:
        # Trim the bulkiest optional blocks first; the pipeline, indicators and position always stay.
        for key in ("evidence", "event_context", "family_weights", "market_anomaly", "lab_context", "context",
                    "mtf_matrix", "data_quality"):
            if key in calcs:
                calcs.pop(key)
                state["engine"] = calcs
                state.setdefault("omitted_for_size", []).append(key)
                text = json.dumps(state, ensure_ascii=False, default=str)
                if len(text) <= MAX_STATE_CHARS:
                    break
        # Still too large (jevos-v4 has an 8192-token context): drop the largest remaining non-core blocks.
        while len(text) > MAX_STATE_CHARS:
            optional = [k for k in calcs if k not in _CORE_KEYS]
            if not optional:
                break
            key = max(optional, key=lambda k: len(json.dumps(calcs[k], ensure_ascii=False, default=str)))
            calcs.pop(key)
            state.setdefault("omitted_for_size", []).append(key)
            text = json.dumps(state, ensure_ascii=False, default=str)
    return state


def state_chars(state: dict[str, Any]) -> int:
    return len(json.dumps(state, ensure_ascii=False, default=str))
