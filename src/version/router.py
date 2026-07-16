"""Version information API router."""

from __future__ import annotations

from fastapi import APIRouter

from src.core.config import settings
from src.version.schemas import VersionResponse
from src.version.utils import get_git_commit_hash

router = APIRouter()


@router.get(
    "/version",
    response_model=VersionResponse,
    tags=["version"],
    summary="Get version information",
    description="Returns the application version, git commit hash, and service name.",
    responses={
        200: {"description": "Version information retrieved successfully"},
        405: {"description": "Method not allowed"},
    },
)
async def get_version() -> VersionResponse:
    """Get version information endpoint.

    Returns the current application version, git commit hash, and service name.
    """
    return VersionResponse(
        version=settings.app_version,
        commit=get_git_commit_hash(),
        service=settings.app_name,
    )
