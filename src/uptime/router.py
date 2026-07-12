"""Uptime API router."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter

from src.core.config import settings
from src.uptime.schemas import UptimeResponse

router = APIRouter()

# Capture the module-level startup time when this router is first imported
_startup_time: datetime = datetime.now(UTC)


@router.get(
    "/uptime",
    response_model=UptimeResponse,
    tags=["uptime"],
    summary="Get service uptime",
    description="Returns the service name, start time, and current uptime in seconds.",
    responses={
        200: {"description": "Uptime information returned successfully"},
    },
)
async def get_uptime() -> UptimeResponse:
    """Get service uptime endpoint.

    Returns the current service uptime information including the service name,
    when it started, and how many seconds it has been running.
    """
    now = datetime.now(UTC)
    uptime_seconds = (now - _startup_time).total_seconds()

    return UptimeResponse(
        service=settings.app_name,
        started_at=_startup_time,
        uptime_seconds=uptime_seconds,
    )
