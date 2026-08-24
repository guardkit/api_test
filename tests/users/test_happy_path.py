"""Happy path tests for user retrieval endpoint.

These tests verify the primary success scenarios for GET /users/{id}:
- AC-001: A valid user ID returns the user details
- AC-002: A user ID that exists returns the user
"""

from __future__ import annotations

from http import HTTPStatus

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.users import crud
from src.users.schemas import UserCreate


class TestHappyPathValidUserIdReturnsDetails:
    """AC-001: A valid user ID returns the user details."""

    @pytest.mark.asyncio
    async def test_valid_user_id_returns_user_details(
        self,
        async_client: AsyncClient,
        override_get_db: None,
        db_session: AsyncSession,
    ) -> None:
        """AC-001: A valid user ID returns the user details.

        Given a valid user ID (UUID format), the GET /users/{id} endpoint
        should return 200 OK with the full user details including id,
        name, email, and other fields.
        """
        # Arrange: create a user with known details
        user_in = UserCreate(
            email="happy.path2@example.com",
            full_name="Happy Path Test User",
        )
        created = await crud.create_user(db_session, user_in)

        # Act: request the user by ID
        response = await async_client.get(f"/users/{created.id}")

        # Assert: response should be 200 OK with user details
        assert response.status_code == HTTPStatus.OK
        data = response.json()

        # Verify all required user detail fields are present
        assert "id" in data
        assert "name" in data
        assert "email" in data
        assert "is_active" in data
        assert "created_at" in data
        assert "updated_at" in data

        # Verify the returned details match what was created
        assert data["id"] == created.id
        assert data["email"] == "happy.path2@example.com"
        assert data["name"] == "Happy Path Test User"
        assert data["is_active"] is True


class TestHappyPathExistingUserReturnsUser:
    """AC-002: A user ID that exists returns the user."""

    @pytest.mark.asyncio
    async def test_existing_user_id_returns_user(
        self,
        async_client: AsyncClient,
        override_get_db: None,
        db_session: AsyncSession,
    ) -> None:
        """AC-002: A user ID that exists returns the user.

        Given a user ID that corresponds to an existing user in the database,
        the GET /users/{id} endpoint should return 200 OK with the user object.
        """
        # Arrange: create a user that will exist in the DB
        user_in = UserCreate(
            email="existing.user@example.com",
            full_name="Existing User",
        )
        existing_user = await crud.create_user(db_session, user_in)

        # Act: retrieve the user by their existing ID
        response = await async_client.get(f"/users/{existing_user.id}")

        # Assert: the response should be 200 OK with the user
        assert response.status_code == HTTPStatus.OK
        data = response.json()

        # Verify the user object is returned correctly
        assert data["id"] == existing_user.id
        assert data["email"] == "existing.user@example.com"
        assert data["name"] == "Existing User"

        # Verify the response is a valid user object (not an error response)
        assert "detail" not in data or "not found" not in data.get("detail", "").lower()

    @pytest.mark.asyncio
    async def test_existing_user_returns_full_object(
        self,
        async_client: AsyncClient,
        override_get_db: None,
        db_session: AsyncSession,
    ) -> None:
        """AC-002: A user ID that exists returns the complete user object.

        The returned user object should contain all expected fields
        and match the stored user data.
        """
        # Arrange: create a user
        user_in = UserCreate(
            email="full.object@example.com",
            full_name="Full Object Test",
        )
        stored_user = await crud.create_user(db_session, user_in)

        # Act: retrieve the user
        response = await async_client.get(f"/users/{stored_user.id}")

        # Assert
        assert response.status_code == HTTPStatus.OK
        data = response.json()

        # Verify all fields of the user object are present and correct
        assert data["id"] == stored_user.id
        assert data["email"] == "full.object@example.com"
        assert data["name"] == "Full Object Test"
        assert data["full_name"] == "Full Object Test"
        assert data["is_active"] is True
        assert isinstance(data["created_at"], str)
        assert isinstance(data["updated_at"], str)
