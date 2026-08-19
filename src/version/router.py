"""Version information API router."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException

from src.core.config import settings
from src.version.schemas import VersionResponse
from src.version.utils import get_git_commit_hash

router = APIRouter()


def _accept_json_header(accept: Optional[str] = Header(default=None)) -> None:
    """Dependency to enforce application/json Accept header.

    Returns 406 Not Acceptable when the Accept header does not include
    application/json.

    Args:
        accept: The Accept header value from the request.

    Raises:
        HTTPException: 406 if application/json is not in the Accept header.
    """
    if accept is None or "application/json" not in accept:
        raise HTTPException(
            status_code=406,
            detail="Not Acceptable: application/json is required",
        )


@router.get(
    "/version",
    response_model=VersionResponse,
    tags=["version"],
    summary="Get version information",
    description="Returns the application version, git commit hash, and service name.",
    responses={
        200: {"description": "Version information retrieved successfully"},
        405: {"description": "Method not allowed"},
        406: {"description": "Not Acceptable: unsupported media type"},
    },
    dependencies=[Depends(_accept_json_header)],
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
