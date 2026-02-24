"""Health check API router."""

from __future__ import annotations

from fastapi import APIRouter

from src.core.config import settings
from src.health.schemas import HealthResponse

router = APIRouter()


@router.get(
    "/health",
    response_model=HealthResponse,
    tags=["health"],
)
async def health_check() -> HealthResponse:
    """Health check endpoint."""
    return HealthResponse(
        status="ok",
        version=settings.app_version,
    )
