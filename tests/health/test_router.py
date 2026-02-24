"""Tests for the health check router."""

from __future__ import annotations

from http import HTTPStatus

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_endpoint_returns_200(async_client: AsyncClient) -> None:
    """Test that GET /health returns HTTP 200."""
    response = await async_client.get("/health")

    assert response.status_code == HTTPStatus.OK


@pytest.mark.asyncio
async def test_health_endpoint_response_body(async_client: AsyncClient) -> None:
    """Test that GET /health returns the correct response body."""
    response = await async_client.get("/health")
    data = response.json()

    assert data == {
        "status": "ok",
        "version": "0.1.0",
    }


@pytest.mark.asyncio
async def test_health_endpoint_content_type(async_client: AsyncClient) -> None:
    """Test that GET /health returns application/json content type."""
    response = await async_client.get("/health")

    assert response.headers["content-type"] == "application/json"
