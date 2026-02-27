"""Tests for the health check router."""

from __future__ import annotations

from http import HTTPStatus

import pytest
from fastapi import FastAPI
from httpx import AsyncClient

from src.db.dependencies import get_db as app_get_db


@pytest.mark.asyncio
async def test_health_endpoint_includes_logging_config(
    async_client: AsyncClient, override_get_db: None
) -> None:
    """Test that GET /health includes logging configuration fields."""
    response = await async_client.get("/health")
    data = response.json()

    # Verify logging config fields are present
    assert "log_level" in data
    assert "log_format" in data

    # Verify values match expected settings
    assert data["log_level"] == "INFO"
    assert data["log_format"] == "json"


@pytest.mark.asyncio
async def test_health_endpoint_returns_200(
    async_client: AsyncClient, override_get_db: None
) -> None:
    """Test that GET /health returns HTTP 200."""
    response = await async_client.get("/health")

    assert response.status_code == HTTPStatus.OK


@pytest.mark.asyncio
async def test_health_endpoint_response_body(
    async_client: AsyncClient, override_get_db: None
) -> None:
    """Test that GET /health returns the correct response body."""
    response = await async_client.get("/health")
    data = response.json()

    assert data == {
        "status": "ok",
        "version": "0.1.0",
        "log_level": "INFO",
        "log_format": "json",
        "database": "connected",
    }


@pytest.mark.asyncio
async def test_health_endpoint_content_type(
    async_client: AsyncClient, override_get_db: None
) -> None:
    """Test that GET /health returns application/json content type."""
    response = await async_client.get("/health")

    assert response.headers["content-type"] == "application/json"


@pytest.mark.asyncio
async def test_health_endpoint_database_connected(
    async_client: AsyncClient, override_get_db: None
) -> None:
    """Test that GET /health returns database connected when DB is reachable."""
    response = await async_client.get("/health")
    data = response.json()

    assert data["status"] == "ok"
    assert data["database"] == "connected"


"""Tests for the health check router."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from http import HTTPStatus

import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.dependencies import get_db as app_get_db


@pytest.mark.asyncio
async def test_health_endpoint_includes_logging_config(
    async_client: AsyncClient, override_get_db: None
) -> None:
    """Test that GET /health includes logging configuration fields."""
    response = await async_client.get("/health")
    data = response.json()

    # Verify logging config fields are present
    assert "log_level" in data
    assert "log_format" in data

    # Verify values match expected settings
    assert data["log_level"] == "INFO"
    assert data["log_format"] == "json"


@pytest.mark.asyncio
async def test_health_endpoint_returns_200(
    async_client: AsyncClient, override_get_db: None
) -> None:
    """Test that GET /health returns HTTP 200."""
    response = await async_client.get("/health")

    assert response.status_code == HTTPStatus.OK


@pytest.mark.asyncio
async def test_health_endpoint_response_body(
    async_client: AsyncClient, override_get_db: None
) -> None:
    """Test that GET /health returns the correct response body."""
    response = await async_client.get("/health")
    data = response.json()

    assert data == {
        "status": "ok",
        "version": "0.1.0",
        "log_level": "INFO",
        "log_format": "json",
        "database": "connected",
    }


@pytest.mark.asyncio
async def test_health_endpoint_content_type(
    async_client: AsyncClient, override_get_db: None
) -> None:
    """Test that GET /health returns application/json content type."""
    response = await async_client.get("/health")

    assert response.headers["content-type"] == "application/json"


@pytest.mark.asyncio
async def test_health_endpoint_database_connected(
    async_client: AsyncClient, override_get_db: None
) -> None:
    """Test that GET /health returns database connected when DB is reachable."""
    response = await async_client.get("/health")
    data = response.json()

    assert data["status"] == "ok"
    assert data["database"] == "connected"


@pytest.mark.asyncio
async def test_health_endpoint_database_unavailable(
    async_client: AsyncClient, db_engine: None
) -> None:
    """Test that GET /health returns database unavailable when probe fails."""

    async def failing_get_db() -> AsyncGenerator[FailingAsyncSession, None]:
        """A get_db dependency that simulates a failed database connection."""

        class FailingAsyncSession:
            """A mock session that fails on execute."""

            async def execute(
                self, statement: object, *args: object, **kwargs: object
            ) -> None:
                raise SQLAlchemyError("Database connection failed")

            async def commit(self) -> None:  # noqa: D401
                pass

            async def rollback(self) -> None:  # noqa: D401
                pass

            async def close(self) -> None:  # noqa: D401
                pass

            def __aiter__(self) -> FailingAsyncSession:  # noqa: D401
                return self

            async def __anext__(self) -> None:  # noqa: D401
                raise StopAsyncIteration

        session = FailingAsyncSession()
        try:
            yield session
        finally:
            await session.close()

    from src.main import app as main_app

    main_app.dependency_overrides[app_get_db] = failing_get_db

    try:
        response = await async_client.get("/health")
        data = response.json()

        # Should still return HTTP 200
        assert response.status_code == HTTPStatus.OK
        assert data["status"] == "degraded"
        assert data["database"] == "unavailable"
    finally:
        # Clean up override
        if app_get_db in main_app.dependency_overrides:
            del main_app.dependency_overrides[app_get_db]
