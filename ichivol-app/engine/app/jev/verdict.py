"""Verdict IchiVol — code turns JEV's typed answers into Ève's action. Thresholds live here, not in JEV.

Ève trades her own paper accounts: the engine computes and presents its calculations, Ève decides, the paper
broker executes what the Risk Kernel and kill switch allow. When she cannot decide (JEV unavailable, or a lean
below the thresholds) she abstains when flat and keeps what she holds; the engine never takes her place. Every
Dossier also records what the engine alone would have done, so Ève is compared with the engine on the same bars.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

DEFAULT_THRESHOLDS: dict[str, float] = {
    "min_choice_prob": 0.55,  # P(long) or P(short) needed to open
    "min_confidence": 0.40,  # JEV confidence on the decision
    "min_quality": 1.5,  # quality SCORE (0..4) needed to open
    "max_contradiction": 0.85,  # Challenger veto: P(material contradiction) above this blocks an open
    "min_close_prob": 0.55,  # P(close) needed to liquidate
}

ACTIONS = ("LONG", "SHORT", "ABSTAIN", "HOLD", "CLOSE", "UNAVAILABLE")

_ENGINE_DIR = {"BUY": "LONG", "SELL": "SHORT"}


@dataclass
class EveVerdict:
    action: str  # LONG | SHORT | ABSTAIN | HOLD | CLOSE | UNAVAILABLE
    label: str  # CONCORDANT | DISCORDANT | RESERVE | INDISPONIBLE
    coherence: float | None  # Indice de cohérence 0..1 (agreement between Ève's judgments) — not a probability
    p_up: float | None  # JEV's P(long) when asked, for calibration
    reasons: list[str] = field(default_factory=list)
    decisive: bool = True  # False = JEV unavailable or leaning below the thresholds (engine takes over in combinaison)

    def to_dict(self) -> dict[str, Any]:
        return {"action": self.action, "label": self.label, "coherence": self.coherence, "p_up": self.p_up,
                "reasons": self.reasons, "decisive": self.decisive}


def _thr(overrides: dict[str, Any] | None) -> dict[str, float]:
    t = dict(DEFAULT_THRESHOLDS)
    for k, v in (overrides or {}).items():
        if k in t and isinstance(v, (int, float)):
            t[k] = float(v)
    return t


def _label(action: str, engine_decision: str | None, holding: str | None) -> str:
    eng = _ENGINE_DIR.get(engine_decision or "")
    if action == "UNAVAILABLE":
        return "INDISPONIBLE"
    if holding:
        engine_keeps = eng == holding
        return "CONCORDANT" if (action == "HOLD") == engine_keeps else "DISCORDANT"
    if action in ("LONG", "SHORT"):
        if eng == action:
            return "CONCORDANT"
        return "DISCORDANT" if eng is not None else "RESERVE"
    return "CONCORDANT" if eng is None else "DISCORDANT"


def _coherence(parts: list[float]) -> float | None:
    vals = [max(0.0, min(1.0, p)) for p in parts if p is not None]
    return round(sum(vals) / len(vals), 3) if vals else None


def decide_entry(
    answers: dict[str, dict[str, Any]] | None,
    *,
    engine_decision: str | None,
    thresholds: dict[str, Any] | None = None,
) -> EveVerdict:
    t = _thr(thresholds)
    a = answers or {}
    dec = a.get("decision")
    if not dec:
        return EveVerdict("UNAVAILABLE", "INDISPONIBLE", None, None, ["JEV n'a pas répondu."], decisive=False)
    probs = dec.get("probabilities") or {}
    choice = dec.get("choice")
    p_long = float(probs.get("long", 0.0))
    p_short = float(probs.get("short", 0.0))
    conf = float(dec.get("confidence", 0.0))
    quality = (a.get("quality") or {}).get("score")
    contradiction = (a.get("contradiction") or {}).get("noul")
    reasons: list[str] = []
    action = "ABSTAIN"
    decisive = True
    if choice in ("long", "short"):
        p = p_long if choice == "long" else p_short
        side = "LONG" if choice == "long" else "SHORT"
        decisive = False
        if p < t["min_choice_prob"]:
            reasons.append(f"Ève penche {side} mais trop faiblement ({p:.0%} < {t['min_choice_prob']:.0%}).")
        elif conf < t["min_confidence"]:
            reasons.append(f"Confiance de JEV insuffisante ({conf:.2f}).")
        elif isinstance(quality, (int, float)) and quality < t["min_quality"]:
            reasons.append(f"Qualité de l'opportunité trop basse ({quality:.1f}/4).")
        elif isinstance(contradiction, (int, float)) and contradiction > t["max_contradiction"]:
            reasons.append(f"Le Challenger voit une contradiction forte ({contradiction:.0%}).")
        else:
            action = side
            decisive = True
            reasons.append(f"Ève décide {side} : probabilité {p:.0%}, confiance {conf:.2f}"
                           + (f", qualité {quality:.1f}/4." if isinstance(quality, (int, float)) else "."))
    else:
        reasons.append("Ève choisit de ne rien faire (abstention).")
    # Coherence: decision certainty, quality, absence of contradiction, agreement with the engine's staged verdict.
    parts: list[float] = [conf]
    if isinstance(quality, (int, float)):
        parts.append(quality / 4.0)
    if isinstance(contradiction, (int, float)):
        parts.append(1.0 - contradiction)
    sup = (a.get("engine_supported") or {}).get("noul")
    if isinstance(sup, (int, float)):
        parts.append(sup if _ENGINE_DIR.get(engine_decision or "") == action else 1.0 - sup)
    return EveVerdict(action, _label(action, engine_decision, None), _coherence(parts), round(p_long, 4), reasons,
                      decisive=decisive)


def decide_manage(
    answers: dict[str, dict[str, Any]] | None,
    *,
    holding: str,
    engine_decision: str | None,
    thresholds: dict[str, Any] | None = None,
) -> EveVerdict:
    t = _thr(thresholds)
    a = answers or {}
    man = a.get("manage")
    if not man:
        return EveVerdict("UNAVAILABLE", "INDISPONIBLE", None, None, ["JEV n'a pas répondu."], decisive=False)
    p_close = float((man.get("probabilities") or {}).get("close", 0.0))
    conf = float(man.get("confidence", 0.0))
    if man.get("choice") == "close" and p_close >= t["min_close_prob"]:
        action, reasons = "CLOSE", [f"Ève liquide la position {holding} (probabilité {p_close:.0%})."]
    else:
        action, reasons = "HOLD", [f"Ève garde la position {holding} (probabilité de clôture {p_close:.0%})."]
    parts: list[float] = [conf]
    risk = (a.get("position_risk") or {}).get("score")
    thesis = (a.get("thesis_valid") or {}).get("noul")
    if isinstance(thesis, (int, float)):
        parts.append(thesis if action == "HOLD" else 1.0 - thesis)
    if isinstance(risk, (int, float)):
        parts.append(1.0 - risk / 3.0 if action == "HOLD" else risk / 3.0)
    return EveVerdict(action, _label(action, engine_decision, holding), _coherence(parts), None, reasons)


def pipeline_decision_for(action: str, holding: str | None) -> str | None:
    """Translate Ève's action into the decision string ``sync_position`` executes. None = leave untouched."""
    if action == "LONG":
        return "BUY"
    if action == "SHORT":
        return "SELL"
    if action == "CLOSE" or action == "ABSTAIN":
        return "NO_TRADE"
    if action == "HOLD" and holding:
        return "BUY" if holding == "LONG" else "SELL"
    if action == "UNAVAILABLE":
        # Keep what is held, open nothing.
        return ("BUY" if holding == "LONG" else "SELL") if holding else "NO_TRADE"
    return None


def engine_action(engine_decision: str | None, holding: str | None) -> str:
    """What the engine alone would do, in Ève's vocabulary."""
    eng = _ENGINE_DIR.get(engine_decision or "")
    if holding:
        return "HOLD" if eng == holding else "CLOSE"
    return eng or "ABSTAIN"


def execute(verdict: EveVerdict, *, holding: str | None) -> tuple[str, str]:
    """(action executed in Ève's account, decided_by). Undecided → abstain when flat, hold what is held."""
    if verdict.decisive and verdict.action != "UNAVAILABLE":
        return verdict.action, "eve"
    return ("HOLD" if holding else "ABSTAIN"), "eve_indecise"
