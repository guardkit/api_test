"""Health check API router."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.db.dependencies import get_db
from src.health.schemas import HealthResponse

router = APIRouter()


@router.get(
    "/health",
    response_model=HealthResponse,
    tags=["health"],
    summary="Check service health",
    description="Returns the current health status, version, logging configuration, and database connectivity status of the API service.",
    responses={
        200: {"description": "Service is healthy"},
    },
)
async def health_check(db: AsyncSession = Depends(get_db)) -> HealthResponse:
    """Health check endpoint.

    Returns the current service health status including database connectivity.
    When the database is unreachable, returns status "degraded" with database "unavailable".
    """
    # Probe database connection
    db_status = "connected"
    try:
        result = await db.execute(text("SELECT 1"))
        result.fetchone()
    except SQLAlchemyError:
        db_status = "unavailable"

    return HealthResponse(
        status="ok" if db_status == "connected" else "degraded",
        version=settings.app_version,
        log_level=settings.log_level,
        log_format=settings.log_format,
        database=db_status,
    )
