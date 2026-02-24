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
    summary="Check service health",
    description="Returns the current health status and version of the API service.",
    responses={
        200: {"description": "Service is healthy"},
    },
)
async def health_check() -> HealthResponse:
    """Health check endpoint."""
    return HealthResponse(
        status="ok",
        version=settings.app_version,
    )
