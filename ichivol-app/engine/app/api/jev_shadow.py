"""API JEV Shadow — observation uniquement."""
import os
from fastapi import APIRouter, HTTPException
from app.api.decisions import get_decision
from app.jev.shadow import compare_decision
from app.jev.history import list_evaluations

router = APIRouter(prefix="/api/engine", tags=["jev-shadow"])

@router.get("/jev-shadow/history")
def get_shadow_history(limit: int = 50) -> dict:
    if os.getenv("JEV_SHADOW_ENABLED", "false").lower() != "true":
        raise HTTPException(status_code=503, detail="jev_shadow_disabled")
    return {"results": list_evaluations(limit)}

@router.get("/jev-shadow/{symbol}")
def evaluate_shadow(symbol: str, timeframe: str = "1h") -> dict:
    if not symbol.replace("-", "").replace("_", "").isalnum():
        raise HTTPException(status_code=422, detail="Invalid symbol")
    if os.getenv("JEV_SHADOW_ENABLED", "false").lower() != "true":
        raise HTTPException(status_code=503, detail="jev_shadow_disabled")
    data = get_decision(symbol=symbol, timeframe=timeframe, persist=False)
    return compare_decision(data)
