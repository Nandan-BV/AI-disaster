import logging

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import text
from app.database import get_db
from app.ai.llm import get_llm_client
from app.config import settings


router = APIRouter(tags=["health"])
logger = logging.getLogger(__name__)


@router.get("/health", response_model=None)
async def health_check(db: AsyncSession = Depends(get_db)) -> dict | JSONResponse:
    try:
        await db.execute(text("SELECT 1"))
    except (SQLAlchemyError, ConnectionError):
        logger.warning("Database health check failed", exc_info=True)
        return JSONResponse(
            status_code=503,
            content={
                "status": "degraded",
                "project": "RESQ-AI",
                "database": "disconnected",
                "copilot": "unknown",
            },
        )

    copilot_status = "not_required"
    if settings.COPILOT_PROVIDER != "mock":
        client = get_llm_client()
        health_probe = getattr(client, "health_check", None)
        if callable(health_probe):
            copilot_status = "available" if await health_probe() else "unavailable"
        else:
            copilot_status = "available" if client.is_available() else "unavailable"

    return {
        "status": "degraded" if copilot_status == "unavailable" else "ok",
        "project": "RESQ-AI",
        "database": "connected",
        "copilot": copilot_status,
    }