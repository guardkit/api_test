"""Tests for the whoami router."""

from __future__ import annotations

from http import HTTPStatus

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from src.whoami.router import router


@pytest.fixture
def test_app() -> FastAPI:
    """Create a test FastAPI app with the whoami router."""
    app = FastAPI()
    app.include_router(router)
    return app


@pytest.mark.asyncio
async def test_whoami_get_returns_200(test_app: FastAPI) -> None:
    """Test that GET /whoami returns HTTP 200."""
    async with AsyncClient(
        transport=ASGITransport(app=test_app), base_url="http://test"
    ) as client:
        response = await client.get("/whoami")

    assert response.status_code == HTTPStatus.OK


@pytest.mark.asyncio
async def test_whoami_get_returns_correct_json(test_app: FastAPI) -> None:
    """Test that GET /whoami returns the correct JSON body."""
    async with AsyncClient(
        transport=ASGITransport(app=test_app), base_url="http://test"
    ) as client:
        response = await client.get("/whoami")

    data = response.json()

    assert data == {"service": "api_test"}


@pytest.mark.asyncio
async def test_whoami_get_content_type(test_app: FastAPI) -> None:
    """Test that GET /whoami returns application/json content type."""
    async with AsyncClient(
        transport=ASGITransport(app=test_app), base_url="http://test"
    ) as client:
        response = await client.get("/whoami")

    assert response.headers["content-type"] == "application/json"


@pytest.mark.asyncio
async def test_whoami_post_returns_405(test_app: FastAPI) -> None:
    """Test that POST /whoami returns 405 Method Not Allowed."""
    async with AsyncClient(
        transport=ASGITransport(app=test_app), base_url="http://test"
    ) as client:
        response = await client.post("/whoami")

    assert response.status_code == HTTPStatus.METHOD_NOT_ALLOWED
