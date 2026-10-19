import logging

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import text
from app.database import get_db


router = APIRouter(tags=["health"])
logger = logging.getLogger(__name__)


@router.get("/health", response_model=None)
async def health_check(db: AsyncSession = Depends(get_db)) -> dict | JSONResponse:
    try:
        await db.execute(text("SELECT 1"))
    except SQLAlchemyError:
        logger.warning("Database health check failed", exc_info=True)
        return JSONResponse(
            status_code=503,
            content={
                "status": "degraded",
                "project": "RESQ-AI",
                "database": "disconnected",
            },
        )

    return {
        "status": "ok",
        "project": "RESQ-AI",
        "database": "connected",
    }