from contextlib import asynccontextmanager
import asyncio
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import OperationalError
from app.config import settings
from app.database import AsyncSessionLocal, close_db
from app.services.external_ingestion import poll_external_feeds
from app.api import (
    analysis,
    auth,
    copilot,
    dashboard,
    events,
    geospatial,
    health,
    incidents,
    investigation,
    optimization,
    resources,
    risk,
)

logger = logging.getLogger(__name__)


async def _run_external_ingestion_scheduler() -> None:
    interval_seconds = settings.EXTERNAL_INGESTION_INTERVAL_MINUTES * 60
    while True:
        await asyncio.sleep(interval_seconds)
        try:
            async with AsyncSessionLocal() as db:
                result = await poll_external_feeds(db)
            if any(
                source.get("status") == "error"
                for source in result["sources"].values()
            ):
                logger.error("One or more external disaster feeds failed: %s", result)
            else:
                logger.info("External disaster feed poll completed: %s", result)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Unexpected error while polling external disaster feeds.")


@asynccontextmanager
async def lifespan(app: FastAPI):
    ingestion_task = None
    if settings.EXTERNAL_INGESTION_ENABLED:
        ingestion_task = asyncio.create_task(_run_external_ingestion_scheduler())
    try:
        yield
    finally:
        if ingestion_task is not None:
            ingestion_task.cancel()
            try:
                await ingestion_task
            except asyncio.CancelledError:
                pass
        await close_db()


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    lifespan=lifespan,
)


@app.exception_handler(ConnectionError)
@app.exception_handler(OperationalError)
async def handle_database_unavailable(
    request,
    exc: OperationalError | ConnectionError,
) -> JSONResponse:
    logger.error("Database request failed because the database is unavailable.")
    return JSONResponse(
        status_code=503,
        content={"detail": "Database service is unavailable."},
    )


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix=settings.API_V1_PREFIX)
app.include_router(auth.router, prefix=settings.API_V1_PREFIX)
app.include_router(events.router, prefix=settings.API_V1_PREFIX)
app.include_router(events.websocket_router)
app.include_router(analysis.router, prefix=settings.API_V1_PREFIX)
app.include_router(geospatial.router, prefix=settings.API_V1_PREFIX)
app.include_router(incidents.router, prefix=settings.API_V1_PREFIX)
app.include_router(investigation.router, prefix=settings.API_V1_PREFIX)
app.include_router(risk.router, prefix=settings.API_V1_PREFIX)
app.include_router(resources.router, prefix=settings.API_V1_PREFIX)
app.include_router(optimization.router, prefix=settings.API_V1_PREFIX)
app.include_router(copilot.router, prefix=settings.API_V1_PREFIX)
app.include_router(dashboard.router, prefix=settings.API_V1_PREFIX)