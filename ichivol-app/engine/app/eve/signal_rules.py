"""Code-side signal gates (Gamma jev-signals-lab) — paper only.

JEV answers are observations; the trade rule lives in code (AND gates).
Never opens risk.
"""

from __future__ import annotations

from typing import Any

SIGNAL_RULES_VERSION = "ichivol.eve.signal_rules.v1"

# Gamma-adapted portable thresholds (long bias). Short mirrors via invert.
LONG_GATES = {
    "trend_bullish": (">", 0.75),
    "momentum_positive": (">", 0.70),
    "relative_strength_positive": (">", 0.65),
    "event_risk": ("<", 0.40),
    "asset_overextended": ("<", 0.80),
}

RULE_STRING = (
    "trend > .75 · momentum > .70 · relative strength > .65 · "
    "event risk < .40 · overextended < .80"
)


def _noul(answers: dict[str, Any], key: str) -> float | None:
    raw = answers.get(key)
    if isinstance(raw, dict):
        if isinstance(raw.get("noul"), (int, float)):
            return float(raw["noul"])
        if isinstance(raw.get("score"), (int, float)):
            # SCORE 0..4 → rough [0,1]
            return min(1.0, max(0.0, float(raw["score"]) / 4.0))
        if isinstance(raw.get("confidence"), (int, float)) and raw.get("choice"):
            return float(raw["confidence"])
    if isinstance(raw, (int, float)):
        return float(raw)
    return None


def extract_signal_nouls(jev_pack: dict[str, Any] | None) -> dict[str, float]:
    """Flatten NOUL/SCORE answers across modes into portable signal ids."""
    out: dict[str, float] = {}
    if not isinstance(jev_pack, dict):
        return out
    for env in jev_pack.values():
        if not isinstance(env, dict) or not env.get("ok"):
            continue
        answers = env.get("answers")
        if not isinstance(answers, dict):
            continue
        for key, ans in answers.items():
            val = _noul({key: ans}, key)
            if val is not None:
                out[str(key)] = val
    return out


def evaluate_long_gates(signals: dict[str, float]) -> dict[str, Any]:
    """AND gates for a paper LONG. Missing signal → fail-closed."""
    checks: list[dict[str, Any]] = []
    ok = True
    for key, (op, thr) in LONG_GATES.items():
        val = signals.get(key)
        if val is None:
            checks.append({"key": key, "pass": False, "reason": "missing"})
            ok = False
            continue
        passed = (val > thr) if op == ">" else (val < thr)
        checks.append({"key": key, "value": val, "op": op, "threshold": thr, "pass": passed})
        if not passed:
            ok = False
    return {
        "schema": SIGNAL_RULES_VERSION,
        "side": "LONG",
        "allowed": ok,
        "decision": "pass" if ok else "reject",
        "reason": None if ok else "signal_rules_long_and_failed",
        "rule": RULE_STRING,
        "checks": checks,
        "signals": signals,
    }


def evaluate_short_gates(signals: dict[str, float]) -> dict[str, Any]:
    """Short = invert bullish/momentum/RS; keep event_risk / overextended caps."""
    inverted = dict(signals)
    for key in ("trend_bullish", "momentum_positive", "relative_strength_positive"):
        if key in inverted:
            inverted[key] = 1.0 - inverted[key]
    out = evaluate_long_gates(inverted)
    out["side"] = "SHORT"
    if not out["allowed"]:
        out["reason"] = "signal_rules_short_and_failed"
    return out


def apply_signal_rules(
    action: str,
    jev_pack: dict[str, Any] | None,
    *,
    required_keys: tuple[str, ...] | None = None,
) -> dict[str, Any]:
    """If action is LONG/SHORT and portable signals present, enforce AND gates.

    When required portable keys are absent, skip (do not block) — Analyst may
    not have asked the Gamma set yet. Fail-closed only when keys are present
    enough to evaluate, or when ``required_keys`` is explicit and missing.
    """
    act = (action or "").upper()
    signals = extract_signal_nouls(jev_pack)
    keys = required_keys or tuple(LONG_GATES.keys())
    present = sum(1 for k in keys if k in signals)
    if present < 3:
        return {
            "schema": SIGNAL_RULES_VERSION,
            "decision": "skip",
            "allowed": True,
            "reason": "insufficient_portable_signals",
            "signals_present": present,
            "rule": RULE_STRING,
        }
    if act == "LONG":
        return evaluate_long_gates(signals)
    if act == "SHORT":
        return evaluate_short_gates(signals)
    return {
        "schema": SIGNAL_RULES_VERSION,
        "decision": "skip",
        "allowed": True,
        "reason": "non_directional",
        "rule": RULE_STRING,
    }
