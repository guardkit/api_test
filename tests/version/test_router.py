"""Tests for the version information router."""

from __future__ import annotations

from http import HTTPStatus

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_version_endpoint_returns_200(async_client: AsyncClient) -> None:
    """Test that GET /version returns HTTP 200."""
    response = await async_client.get("/version")

    assert response.status_code == HTTPStatus.OK


@pytest.mark.asyncio
async def test_version_endpoint_response_structure(
    async_client: AsyncClient,
) -> None:
    """Test that GET /version returns JSON with version, commit, and service keys."""
    response = await async_client.get("/version")
    data = response.json()

    # AC-001: Verify required keys are present
    assert "version" in data
    assert "commit" in data
    assert "service" in data

    # Verify all keys are present and only these keys
    assert set(data.keys()) == {"version", "commit", "service"}


@pytest.mark.asyncio
async def test_version_endpoint_response_values(
    async_client: AsyncClient,
) -> None:
    """Test that GET /version returns correct application version and service name."""
    response = await async_client.get("/version")
    data = response.json()

    # AC-002: Response contains application version string
    assert isinstance(data["version"], str)
    assert len(data["version"]) > 0

    # AC-002: Response contains 40-character git commit hash (full SHA-1)
    assert isinstance(data["commit"], str)
    # Commit should be either "unknown" or a 40-character hex string
    if data["commit"] != "unknown":
        assert len(data["commit"]) == 40
        assert all(c in "0123456789abcdef" for c in data["commit"].lower())

    # AC-004: Response contains service name
    assert isinstance(data["service"], str)
    assert len(data["service"]) > 0


@pytest.mark.asyncio
async def test_version_endpoint_content_type(async_client: AsyncClient) -> None:
    """Test that GET /version returns application/json content type."""
    response = await async_client.get("/version")

    assert "application/json" in response.headers["content-type"]


@pytest.mark.asyncio
async def test_version_endpoint_post_not_allowed(async_client: AsyncClient) -> None:
    """Test that POST /version returns 405 Method Not Allowed."""
    response = await async_client.post("/version")

    # AC-005: All non-GET methods return 405 Method Not Allowed
    assert response.status_code == HTTPStatus.METHOD_NOT_ALLOWED


@pytest.mark.asyncio
async def test_version_endpoint_put_not_allowed(async_client: AsyncClient) -> None:
    """Test that PUT /version returns 405 Method Not Allowed."""
    response = await async_client.put("/version")

    # AC-005: All non-GET methods return 405 Method Not Allowed
    assert response.status_code == HTTPStatus.METHOD_NOT_ALLOWED


@pytest.mark.asyncio
async def test_version_endpoint_delete_not_allowed(async_client: AsyncClient) -> None:
    """Test that DELETE /version returns 405 Method Not Allowed."""
    response = await async_client.delete("/version")

    # AC-005: All non-GET methods return 405 Method Not Allowed
    assert response.status_code == HTTPStatus.METHOD_NOT_ALLOWED


@pytest.mark.asyncio
async def test_version_endpoint_patch_not_allowed(async_client: AsyncClient) -> None:
    """Test that PATCH /version returns 405 Method Not Allowed."""
    response = await async_client.patch("/version")
    assert response.status_code == HTTPStatus.METHOD_NOT_ALLOWED


@pytest.mark.asyncio
async def test_version_endpoint_unsupported_media_type_returns_406(
    async_client: AsyncClient,
) -> None:
    """Test that GET /version with unsupported Accept header returns 406 Not Acceptable.

    FastAPI's response_model validation enforces that responses match the expected
    content type. When a client sends an Accept header that does not include
    application/json, the server should respond with 406 Not Acceptable.
    """
    response = await async_client.get("/version", headers={"Accept": "text/plain"})

    assert response.status_code == HTTPStatus.NOT_ACCEPTABLE

    # AC-005: All non-GET methods return 405 Method Not Allowed
