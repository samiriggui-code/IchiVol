from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.routes import router as engine_router
from app.config import settings
from app.screener.cache import screener_cache


@asynccontextmanager
async def lifespan(app: FastAPI):
    screener_cache.start()
    yield
    screener_cache.stop()


app = FastAPI(title="IchiVol Engine", version="0.1.0", lifespan=lifespan)
app.include_router(engine_router)


@app.get(f"{settings.engine_api_prefix}/health")
def health() -> dict:
    return {"status": "ok", "service": "ichivol-engine"}
