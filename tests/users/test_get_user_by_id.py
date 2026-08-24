"""Tests for GET /users/{id} endpoint."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from http import HTTPStatus
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import exc as sqlalchemy_exc
from sqlalchemy.ext.asyncio import AsyncSession

from src.db.dependencies import get_db as app_get_db
from src.main import app


class TestGetUserById:
    """Tests for GET /users/{id} endpoint."""

    @pytest.mark.asyncio
    async def test_get_user_returns_name_field(
        self,
        async_client: AsyncClient,
        override_get_db: None,
        db_session: AsyncSession,
    ) -> None:
        """GET /users/{id} response includes id, name, and email per ASSUM-001.

        The response body must contain id, name, and email fields when
        retrieving a valid user by their UUID.
        """
        from src.users import crud
        from src.users.schemas import UserCreate

        user_in = UserCreate(
            email="name-field@example.com",
            full_name="Name Field Test",
        )
        created = await crud.create_user(db_session, user_in)

        response = await async_client.get(f"/users/{created.id}")

        assert response.status_code == HTTPStatus.OK
        data = response.json()

        assert "id" in data
        assert "name" in data
        assert "email" in data
        assert data["id"] == created.id
        assert data["name"] == "Name Field Test"
        assert data["email"] == "name-field@example.com"

    @pytest.fixture
    def broken_get_db_override(self) -> AsyncGenerator[None, None]:
        """Override get_db with a broken session that raises on execute."""
        async def broken_session() -> AsyncGenerator[AsyncSession, None]:
            session = AsyncMock(spec=AsyncSession)
            session.execute.side_effect = sqlalchemy_exc.OperationalError(
                "connection refused", {}, None
            )
            yield session

        app.dependency_overrides[app_get_db] = broken_session
        yield
        # Remove override after test
        if app_get_db in app.dependency_overrides:
            del app.dependency_overrides[app_get_db]

    @pytest.mark.asyncio
    async def test_get_user_db_error_returns_503(
        self,
        async_client: AsyncClient,
        broken_get_db_override: None,
    ) -> None:
        """GET /users/{id} handles database connectivity errors gracefully.

        When the database is unavailable, the endpoint should return
        a 503 Service Unavailable response instead of crashing.
        """
        fake_id = str(uuid4())

        response = await async_client.get(f"/users/{fake_id}")

        assert response.status_code == HTTPStatus.SERVICE_UNAVAILABLE
        data = response.json()
        detail_lower = data["detail"].lower()
        assert "database" in detail_lower or "unavailable" in detail_lower

    @pytest.mark.asyncio
    async def test_get_user_not_found_returns_404(
        self,
        async_client: AsyncClient,
        override_get_db: None,
    ) -> None:
        """GET /users/{id} returns 404 for non-existent user ID."""
        fake_id = str(uuid4())

        response = await async_client.get(f"/users/{fake_id}")

        assert response.status_code == HTTPStatus.NOT_FOUND
        data = response.json()
        assert "not found" in data["detail"].lower()
