"""JEV Shadow — évaluation indépendante, sans exécution."""
import logging
import time
from app.jev.history import save_evaluation
from app.jev.client import evaluate

def compare_decision(data: dict) -> dict:
    pipeline = data.get("pipeline") or {}
    original = pipeline.get("decision") or data.get("decision")
    state = str({"symbol": data.get("symbol"), "timeframe": data.get("timeframe"), "decision": original, "pipeline": pipeline})
    questions = {"review": {"type": "noul", "instructions": "Does the supplied evidence support the existing decision? Assess consistency only. Do not suggest trade execution."}}
    started = time.monotonic()
    result = evaluate(state, questions)
    latency_ms = round((time.monotonic() - started) * 1000, 2)
    try:
        save_evaluation(data.get("symbol") or "UNKNOWN", data.get("timeframe") or "UNKNOWN", original, result, latency_ms)
    except Exception:
        logging.getLogger(__name__).exception("JEV Shadow history unavailable")
    return {"mode": "shadow", "original_decision": original, "jev": result, "execution_allowed": False}
