"""Acceptance tests for the user summary endpoint (GET /users/{user_id}/summary).

These tests validate the core acceptance criteria for the user summary feature:
- AC-001: Happy path (known user, database available)
- AC-002: Unknown user ID (returns 404)
- AC-003: Database unavailable with cached record (returns cached data)
- AC-004: Database unavailable without cached record (returns 404)
- AC-005: Unknown user ID with database unavailable (returns 404)
- AC-006: Unknown user ID with cached record for different user (returns 404)
"""

from __future__ import annotations

import json
from collections.abc import AsyncGenerator
from http import HTTPStatus
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.exc import SQLAlchemyError

from src.db.dependencies import get_db as app_get_db
from src.main import app
from src.users import crud
from src.users.schemas import UserCreate, UserSummaryResponse


class FailingAsyncSession:
    """A mock session that fails on database operations.

    Yields successfully but raises SQLAlchemyError on execute(),
    simulating database unavailability.
    """

    async def execute(self, statement, *args, **kwargs):
        """Execute raises SQLAlchemyError to simulate DB failure."""
        raise SQLAlchemyError("Connection refused")

    async def commit(self):
        """No-op commit."""

    async def rollback(self):
        """No-op rollback."""

    async def close(self):
        """No-op close."""

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


class TestUserSummaryAcceptance:
    """Acceptance tests for GET /users/{user_id}/summary endpoint."""

    @pytest.mark.asyncio
    async def test_ac001_happy_path_known_user_with_database_available(
        self,
        async_client: AsyncClient,
        override_get_db: None,
        db_session,
    ) -> None:
        """AC-001: Test covers happy path (known user, database available).

        When a known user ID is requested and the database is available,
        the endpoint should return a 200 status with the user's summary
        including derived fields like days_since_created and profile metadata.
        """
        # Create a known user in the database
        user_in = UserCreate(
            email="happy.path@example.com",
            full_name="Happy Path User",
        )
        user = await crud.create_user(db_session, user_in)
        await db_session.commit()

        # Request the summary for the known user
        response = await async_client.get(f"/users/{user.id}/summary")

        assert response.status_code == HTTPStatus.OK
        data = response.json()
        assert data["username"] == "happy.path@example.com"
        assert data["display_name"] == "Happy Path User"
        assert data["is_active"] is True
        assert "email" in data["profile_metadata"]
        assert data["profile_metadata"]["email"] == "happy.path@example.com"
        assert data["profile_metadata"]["status"] == "active"
        assert isinstance(data["days_since_created"], int)
        assert data["days_since_created"] >= 0

    @pytest.mark.asyncio
    async def test_ac002_unknown_user_id_returns_404(
        self,
        async_client: AsyncClient,
        override_get_db: None,
    ) -> None:
        """AC-002: Test covers unknown user ID (returns 404).

        When an unknown user ID is requested and the database is available,
        the endpoint should return a 404 status code with a not found message.
        """
        unknown_id = str(uuid4())
        response = await async_client.get(f"/users/{unknown_id}/summary")

        assert response.status_code == HTTPStatus.NOT_FOUND
        data = response.json()
        assert "not found" in data["detail"].lower()

    @pytest.mark.asyncio
    async def test_ac003_database_unavailable_with_cached_record(
        self,
        async_client: AsyncClient,
        db_error_override: None,
    ) -> None:
        """AC-003: Test covers database unavailable with cached record
        (returns cached data).

        When the database is unavailable but the cache contains a record
        for the requested user, the endpoint should return a 200 status
        with the cached user summary data.
        """
        cached_user_id = str(uuid4())
        cached_summary = UserSummaryResponse(
            username="cached@example.com",
            display_name="Cached User",
            profile_metadata={
                "email": "cached@example.com",
                "status": "active",
            },
            days_since_created=42,
            is_active=True,
        )

        mock_client = MagicMock()
        mock_client.get = AsyncMock(
            return_value=json.dumps(cached_summary.model_dump())
        )
        mock_client.close = AsyncMock()

        with patch("redis.asyncio.from_url", return_value=mock_client):
            response = await async_client.get(f"/users/{cached_user_id}/summary")

            assert response.status_code == HTTPStatus.OK
            data = response.json()
            assert data["username"] == "cached@example.com"
            assert data["display_name"] == "Cached User"
            assert data["is_active"] is True
            assert data["days_since_created"] == 42
            assert data["profile_metadata"]["email"] == "cached@example.com"
            assert data["profile_metadata"]["status"] == "active"

    @pytest.mark.asyncio
    async def test_ac004_database_unavailable_without_cached_record(
        self,
        async_client: AsyncClient,
        db_error_override: None,
    ) -> None:
        """AC-004: Test covers database unavailable without cached record (returns 404).

        When the database is unavailable and the cache does not contain
        a record for the requested user, the endpoint should return a 404
        status code indicating the user was not found.
        """
        unknown_id = str(uuid4())
        mock_client = MagicMock()
        mock_client.get = AsyncMock(return_value=None)
        mock_client.close = AsyncMock()

        with patch("redis.asyncio.from_url", return_value=mock_client):
            response = await async_client.get(f"/users/{unknown_id}/summary")

            assert response.status_code == HTTPStatus.NOT_FOUND
            data = response.json()
            assert "not found" in data["detail"].lower()

    @pytest.mark.asyncio
    async def test_ac005_unknown_user_id_with_database_unavailable(
        self,
        async_client: AsyncClient,
        db_error_override: None,
    ) -> None:
        """AC-005: Test covers unknown user ID with database unavailable (returns 404).

        When an unknown user ID is requested and the database is unavailable,
        the endpoint should still return a 404 status code. The cache miss
        (since the user was never queried) confirms the user is unknown.
        """
        unknown_id = str(uuid4())
        mock_client = MagicMock()
        mock_client.get = AsyncMock(return_value=None)
        mock_client.close = AsyncMock()

        with patch("redis.asyncio.from_url", return_value=mock_client):
            response = await async_client.get(f"/users/{unknown_id}/summary")

            assert response.status_code == HTTPStatus.NOT_FOUND
            data = response.json()
            assert "not found" in data["detail"].lower()

    @pytest.mark.asyncio
    async def test_ac006_unknown_user_id_with_cached_record_for_different_user(
        self,
        async_client: AsyncClient,
        db_error_override: None,
    ) -> None:
        """AC-006: Test covers unknown user ID with cached record
        for different user (returns 404).

        When an unknown user ID is requested and the database is unavailable,
        but the cache contains a record for a different user, the endpoint
        should return a 404 status code because the requested user
        is not found.
        """
        unknown_id = str(uuid4())
        # Cache contains a record for a DIFFERENT user
        different_user_id = str(uuid4())
        cached_summary = UserSummaryResponse(
            username="different@example.com",
            display_name="Different User",
            profile_metadata={
                "email": "different@example.com",
                "status": "active",
            },
            days_since_created=100,
            is_active=True,
        )

        mock_client = MagicMock()

        def mock_get(key):
            """Return cached data only for the different user's cache key."""
            if key == f"user:summary:{different_user_id}":
                return json.dumps(cached_summary.model_dump())
            return None

        mock_client.get = AsyncMock(side_effect=mock_get)
        mock_client.close = AsyncMock()

        with patch("redis.asyncio.from_url", return_value=mock_client):
            response = await async_client.get(f"/users/{unknown_id}/summary")

            assert response.status_code == HTTPStatus.NOT_FOUND
            data = response.json()
            assert "not found" in data["detail"].lower()
            # Verify we did NOT get the different user's data
            # (the response is an error, not the cached summary)
            different_username = "different@example.com"
            assert "username" not in data or data.get("username") != different_username
