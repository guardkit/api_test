"""Tests for the health check router."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from http import HTTPStatus

import pytest
from httpx import AsyncClient
from sqlalchemy.exc import SQLAlchemyError

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


class FailingAsyncSession:
    """A mock session that fails on execute."""

    async def execute(self, statement: object, *args: object, **kwargs: object) -> None:
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


@pytest.mark.asyncio
async def test_health_endpoint_database_unavailable(
    async_client: AsyncClient, db_engine: None
) -> None:
    """Test that GET /health returns database unavailable when probe fails."""

    async def failing_get_db() -> AsyncGenerator[FailingAsyncSession, None]:
        """A get_db dependency that simulates a failed database connection."""
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


@pytest.mark.asyncio
async def test_ready_endpoint_returns_200(async_client: AsyncClient) -> None:
    """Test that GET /ready returns HTTP 200 OK."""
    response = await async_client.get("/ready")

    assert response.status_code == HTTPStatus.OK


@pytest.mark.asyncio
async def test_ready_endpoint_response_body(async_client: AsyncClient) -> None:
    """Test that GET /ready returns the correct response body structure."""
    response = await async_client.get("/ready")
    data = response.json()

    # Verify the response has the expected structure
    assert "status" in data
    assert data["status"] == "ready"
    assert "service" in data
    assert isinstance(data["service"], str)
    assert len(data["service"]) > 0


@pytest.mark.asyncio
async def test_ready_endpoint_content_type(async_client: AsyncClient) -> None:
    """Test that GET /ready returns application/json content type."""
    response = await async_client.get("/ready")

    assert response.headers["content-type"] == "application/json"


@pytest.mark.asyncio
async def test_ready_endpoint_post_method_not_allowed(
    async_client: AsyncClient,
) -> None:
    """Test that POST /ready returns HTTP 405 Method Not Allowed.

    This is an invariant test: the /ready endpoint only supports GET requests.
    Any other HTTP method should return 405, regardless of what other endpoints
    or features are added to the application.
    """
    response = await async_client.post("/ready")

    assert response.status_code == HTTPStatus.METHOD_NOT_ALLOWED


@pytest.mark.asyncio
async def test_ready_endpoint_put_method_not_allowed(
    async_client: AsyncClient,
) -> None:
    """Test that PUT /ready returns HTTP 405 Method Not Allowed.

    This verifies the invariant that /ready only accepts GET requests.
    """
    response = await async_client.put("/ready")

    assert response.status_code == HTTPStatus.METHOD_NOT_ALLOWED


@pytest.mark.asyncio
async def test_ready_endpoint_delete_method_not_allowed(
    async_client: AsyncClient,
) -> None:
    """Test that DELETE /ready returns HTTP 405 Method Not Allowed.

    This verifies the invariant that /ready only accepts GET requests.
    """
    response = await async_client.delete("/ready")

    assert response.status_code == HTTPStatus.METHOD_NOT_ALLOWED


@pytest.mark.asyncio
async def test_ready_endpoint_patch_method_not_allowed(
    async_client: AsyncClient,
) -> None:
    """Test that PATCH /ready returns HTTP 405 Method Not Allowed.

    This verifies the invariant that /ready only accepts GET requests.
    """
    response = await async_client.patch("/ready")

    assert response.status_code == HTTPStatus.METHOD_NOT_ALLOWED


@pytest.mark.asyncio
async def test_ready_endpoint_lightweight_no_db_dependency(
    async_client: AsyncClient,
) -> None:
    """Test that GET /ready succeeds without database dependency.

    This verifies that the /ready endpoint is a lightweight check that doesn't
    require database connectivity, making it suitable for Kubernetes readiness
    probes. Unlike /health, it should work even if database dependencies fail.
    """
    response = await async_client.get("/ready")

    # Should succeed regardless of database state
    assert response.status_code == HTTPStatus.OK
    data = response.json()
    assert data["status"] == "ready"


@pytest.mark.asyncio
async def test_ready_endpoint_service_field_matches_app_name(
    async_client: AsyncClient,
) -> None:
    """Test that GET /ready service field matches settings.app_name.

    This verifies that the service identifier in the readiness response
    correctly reflects the configured application name from settings.
    This is an invariant test: the service field should always equal
    settings.app_name regardless of other configuration changes.
    """
    from src.core.config import settings

    response = await async_client.get("/ready")
    data = response.json()

    assert "service" in data
    assert data["service"] == settings.app_name


def test_ready_response_schema_accepts_api_test_service() -> None:
    """Test that ReadyResponse schema can be instantiated with 'api_test' service.

    This test verifies that the ReadyResponse schema correctly accepts
    'api_test' as a valid service identifier value, demonstrating that
    the response body can identify the service appropriately when configured.

    This is an invariant test: the schema should accept any valid string
    as the service name, not just the default 'api' value.
    """
    from src.health.schemas import ReadyResponse

    # Test that schema accepts api_test as service name
    response = ReadyResponse(status="ready", service="api_test")

    assert response.status == "ready"
    assert response.service == "api_test"

    # Verify it serializes correctly
    response_dict = response.model_dump()
    assert response_dict == {"status": "ready", "service": "api_test"}
