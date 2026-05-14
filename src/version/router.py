"""Version API router."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel, Field

from src.core.config import settings


class VersionResponse(BaseModel):
    """Version response model exposing service build metadata."""

    service: str = Field(description="Service name")
    version: str = Field(description="Service semantic version string")
    git_sha: str = Field(description="Git commit SHA the service was built from")
    build_time: str = Field(description="ISO 8601 timestamp when the service was built")


router = APIRouter()


@router.get(
    "/version",
    response_model=VersionResponse,
    tags=["version"],
    summary="Get service version information",
    description="Returns service name, version, git SHA, and build time metadata.",
    responses={
        200: {
            "description": "Service version metadata",
            "content": {
                "application/json": {
                    "example": {
                        "service": "api_test",
                        "version": "0.1.0",
                        "git_sha": "unknown",
                        "build_time": "unknown",
                    }
                }
            },
        },
    },
)
async def get_version() -> VersionResponse:
    """Return the service version metadata."""
    return VersionResponse(
        service=settings.app_name,
        version=settings.app_version,
        git_sha=settings.app_git_sha,
        build_time=settings.app_build_time,
    )
