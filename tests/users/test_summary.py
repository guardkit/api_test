"""Tests for user summary endpoint."""

from __future__ import annotations

from http import HTTPStatus
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.users import crud
from src.users.schemas import UserCreate


class TestGetUserSummary:
    """Tests for GET /users/{user_id}/summary endpoint."""

    @pytest.mark.asyncio
    async def test_summary_returns_200_for_valid_user(
        self, async_client: AsyncClient, override_get_db: None
    ) -> None:
        """Test that GET /users/{user_id}/summary returns 200 for a valid user."""
        user_in = UserCreate(
            email="summary.user@example.com",
            full_name="Summary User",
        )

        # We need to create the user first via the API
        create_response = await async_client.post("/users", json=user_in.model_dump())
        assert create_response.status_code == HTTPStatus.CREATED
        user_data = create_response.json()
        user_id = user_data["id"]

        response = await async_client.get(f"/users/{user_id}/summary")

        assert response.status_code == HTTPStatus.OK

    @pytest.mark.asyncio
    async def test_summary_response_contains_required_fields(
        self, async_client: AsyncClient, override_get_db: None
    ) -> None:
        """Test that response contains username, display name, and profile metadata."""
        user_in = UserCreate(
            email="fields.user@example.com",
            full_name="Fields User",
        )

        create_response = await async_client.post("/users", json=user_in.model_dump())
        user_id = create_response.json()["id"]

        response = await async_client.get(f"/users/{user_id}/summary")
        data = response.json()

        assert "username" in data
        assert "display_name" in data
        assert "profile_metadata" in data
        assert data["username"] == "fields.user@example.com"
        assert data["display_name"] == "Fields User"
        assert isinstance(data["profile_metadata"], dict)

    @pytest.mark.asyncio
    async def test_summary_includes_days_since_created_as_integer(
        self, async_client: AsyncClient, override_get_db: None
    ) -> None:
        """Test that response includes 'days_since_created' as integer."""
        user_in = UserCreate(
            email="days.user@example.com",
            full_name="Days User",
        )

        create_response = await async_client.post("/users", json=user_in.model_dump())
        user_id = create_response.json()["id"]

        response = await async_client.get(f"/users/{user_id}/summary")
        data = response.json()

        assert "days_since_created" in data
        assert isinstance(data["days_since_created"], int)
        assert data["days_since_created"] >= 0

    @pytest.mark.asyncio
    async def test_summary_includes_is_active_boolean(
        self, async_client: AsyncClient, override_get_db: None
    ) -> None:
        """Test that response includes 'is_active' boolean."""
        user_in = UserCreate(
            email="active.user@example.com",
            full_name="Active User",
        )

        create_response = await async_client.post("/users", json=user_in.model_dump())
        user_id = create_response.json()["id"]

        response = await async_client.get(f"/users/{user_id}/summary")
        data = response.json()

        assert "is_active" in data
        assert isinstance(data["is_active"], bool)
        assert data["is_active"] is True

    @pytest.mark.asyncio
    async def test_summary_returns_404_for_nonexistent_user(
        self, async_client: AsyncClient, override_get_db: None
    ) -> None:
        """Test 404 for a non-existent user."""
        fake_id = str(uuid4())
        response = await async_client.get(f"/users/{fake_id}/summary")

        assert response.status_code == HTTPStatus.NOT_FOUND
        data = response.json()
        assert "not found" in data["detail"].lower()

    @pytest.mark.asyncio
    async def test_summary_with_no_full_name(
        self, async_client: AsyncClient, override_get_db: None
    ) -> None:
        """Test summary when user has no full_name set."""
        user_in = UserCreate(
            email="noname.user@example.com",
        )

        create_response = await async_client.post("/users", json=user_in.model_dump())
        user_id = create_response.json()["id"]

        response = await async_client.get(f"/users/{user_id}/summary")
        data = response.json()

        assert data["display_name"] is not None
        assert data["is_active"] is True
        assert isinstance(data["days_since_created"], int)

    @pytest.mark.asyncio
    async def test_summary_inactive_user(
        self, async_client: AsyncClient, override_get_db: None, db_session: AsyncSession
    ) -> None:
        """Test summary for an inactive user."""
        user_in = UserCreate(
            email="inactive.user@example.com",
            full_name="Inactive User",
        )
        user = await crud.create_user(db_session, user_in)

        # Mark user as inactive
        from src.users.schemas import UserUpdate
        await crud.update_user(
            db_session,
            str(user.id),
            UserUpdate(is_active=False),
        )

        response = await async_client.get(f"/users/{user.id}/summary")
        data = response.json()

        assert data["is_active"] is False
        assert data["profile_metadata"]["status"] == "inactive"
