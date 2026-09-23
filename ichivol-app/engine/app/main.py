from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.activity import router as activity_router
from app.api.indicators import router as indicators_router
from app.api.routes import router as engine_router
from app.backtest.evidence import backtest_evidence_scheduler
from app.config import settings
from app.evidence.outcomes import outcome_tracker
from app.paper.protection import protection_monitor
from app.screener.cache import screener_cache


@asynccontextmanager
async def lifespan(app: FastAPI):
    screener_cache.start()
    if settings.enable_backtest_evidence:
        backtest_evidence_scheduler.start()
    if settings.enable_signal_tracking:
        outcome_tracker.start()
    if settings.enable_protection_monitor:
        protection_monitor.interval_s = settings.protection_interval_s
        protection_monitor.start()
    yield
    protection_monitor.stop()
    screener_cache.stop()
    if settings.enable_signal_tracking:
        outcome_tracker.stop()
    if settings.enable_backtest_evidence:
        backtest_evidence_scheduler.stop()


app = FastAPI(title="IchiVol Engine", version="0.1.0", lifespan=lifespan)
# Avant engine_router : /backtest/runs ne doit pas être avalée par /backtest/{symbol}.
app.include_router(activity_router)
app.include_router(indicators_router)
app.include_router(engine_router)


@app.get(f"{settings.engine_api_prefix}/health")
def health() -> dict:
    return {"status": "ok", "service": "ichivol-engine"}
