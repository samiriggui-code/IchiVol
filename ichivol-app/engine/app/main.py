from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes import router as engine_router
from app.backtest.evidence import backtest_evidence_scheduler
from app.config import settings
from app.screener.cache import screener_cache


@asynccontextmanager
async def lifespan(app: FastAPI):
    screener_cache.start()
    if settings.enable_backtest_evidence:
        backtest_evidence_scheduler.start()
    yield
    screener_cache.stop()
    if settings.enable_backtest_evidence:
        backtest_evidence_scheduler.stop()


app = FastAPI(title="IchiVol Engine", version="0.1.0", lifespan=lifespan)
app.include_router(engine_router)


@app.get(f"{settings.engine_api_prefix}/health")
def health() -> dict:
    return {"status": "ok", "service": "ichivol-engine"}
