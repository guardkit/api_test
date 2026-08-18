"""Tests for user summary cache fallback logic."""

from __future__ import annotations

import json
from collections.abc import AsyncGenerator
from http import HTTPStatus
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.exc import SQLAlchemyError

from src.db.dependencies import get_db as app_get_db
from src.main import app
from src.users.schemas import UserSummaryResponse


class FailingAsyncSession:
    """A mock session that fails on database operations."""

    async def execute(self, statement, *args, **kwargs):
        """Execute raises SQLAlchemyError to simulate DB failure."""
        raise SQLAlchemyError("Connection refused")

    async def commit(self):
        pass

    async def rollback(self):
        pass

    async def close(self):
        pass

    def __aiter__(self):
        return self

    async def __anext__(self):
        raise StopAsyncIteration


@pytest.fixture
def db_error_override():
    """Override get_db to yield a failing session during the test.

    The session yields successfully but raises SQLAlchemyError on
    database operations, simulating database unavailability.
    """
    async def failing_get_db() -> AsyncGenerator[FailingAsyncSession, None]:
        session = FailingAsyncSession()
        try:
            yield session
        finally:
            await session.close()

    app.dependency_overrides[app_get_db] = failing_get_db
    yield
    if app_get_db in app.dependency_overrides:
        del app.dependency_overrides[app_get_db]


@pytest.fixture
def mock_redis_client():
    """Provide a mock Redis client with a cached user summary.

    The mock client returns a pre-built user summary when get() is
    called with the expected cache key pattern.
    """
    mock_client = MagicMock()
    mock_client.get = AsyncMock()
    mock_client.set = AsyncMock()
    mock_client.close = AsyncMock()

    summary = UserSummaryResponse(
        username="fallback@example.com",
        display_name="Fallback User",
        profile_metadata={
            "email": "fallback@example.com",
            "status": "active",
        },
        days_since_created=100,
        is_active=True,
    )
    mock_client.get.return_value = json.dumps(summary.model_dump())

    return mock_client


class TestCacheFallback:
    """Tests for cache fallback behavior in the user summary endpoint."""

    @pytest.mark.asyncio
    async def test_fallback_to_cache_on_db_error(
        self,
        async_client: AsyncClient,
        mock_redis_client: MagicMock,
        db_error_override: None,
    ) -> None:
        """Test that the endpoint falls back to cache when the database is unavailable.

        When the database connection fails (SQLAlchemyError), the endpoint
        should attempt to retrieve the user summary from the Redis cache.
        A cache hit should return a 200 response with the cached data.
        """
        with patch("redis.asyncio.from_url") as mock_from_url:
            mock_from_url.return_value = mock_redis_client

            import uuid

            user_id = str(uuid.uuid4())

            response = await async_client.get(f"/users/{user_id}/summary")

            assert response.status_code == HTTPStatus.OK
            data = response.json()
            assert data["username"] == "fallback@example.com"
            assert data["display_name"] == "Fallback User"
            assert data["is_active"] is True
            assert data["days_since_created"] == 100

    @pytest.mark.asyncio
    async def test_404_on_cache_miss_with_db_error(
        self,
        async_client: AsyncClient,
        db_error_override: None,
    ) -> None:
        """Test that a 404 is returned when both database and cache fail.

        When the database is unavailable and the cache does not contain
        the requested user summary, the endpoint should return a 404
        status code indicating the user was not found.
        """
        mock_client = MagicMock()
        mock_client.get = AsyncMock(return_value=None)
        mock_client.close = AsyncMock()

        with patch("redis.asyncio.from_url", return_value=mock_client):
            import uuid

            user_id = str(uuid.uuid4())

            response = await async_client.get(f"/users/{user_id}/summary")

            assert response.status_code == HTTPStatus.NOT_FOUND
            data = response.json()
            assert "not found" in data["detail"].lower()

    @pytest.mark.asyncio
    async def test_cache_key_format(self) -> None:
        """Test that the cache key follows the expected format.

        The cache key should follow the pattern user:summary:{user_id}
        to maintain consistency with other user endpoint cache keys.
        """
        from src.users.router import _cache_key

        user_id = "550e8400-e29b-41d4-a716-446655440000"
        expected = f"user:summary:{user_id}"

        assert _cache_key(user_id) == expected
