"""Tests for the DELETE /users/{user_id} endpoint."""

from __future__ import annotations

from http import HTTPStatus
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.users import crud
from src.users.schemas import UserCreate

AUTH_TOKEN = "dev-token"


class TestDeleteUserById:
    """Tests for DELETE /users/{user_id} endpoint."""

    @pytest.mark.asyncio
    async def test_delete_user_success(
        self,
        async_client: AsyncClient,
        override_get_db: None,
        db_session: AsyncSession,
    ) -> None:
        """Test successful user deletion returns 204."""
        # Create a user to delete
        user_in = UserCreate(email="delete-me@example.com", full_name="Delete Me")
        user = await crud.create_user(db_session, user_in)

        response = await async_client.delete(
            f"/users/{user.id}", headers={"X-Auth-Token": AUTH_TOKEN}
        )

        assert response.status_code == HTTPStatus.NO_CONTENT
        # Verify user is actually deleted
        existing = await crud.get_user(db_session, user.id)
        assert existing is None

    @pytest.mark.asyncio
    async def test_delete_user_non_existent(
        self,
        async_client: AsyncClient,
        override_get_db: None,
    ) -> None:
        """Test deleting a non-existent user returns 404."""
        fake_id = str(uuid4())

        response = await async_client.delete(
            f"/users/{fake_id}", headers={"X-Auth-Token": AUTH_TOKEN}
        )

        assert response.status_code == HTTPStatus.NOT_FOUND
        data = response.json()
        assert "not found" in data["detail"].lower()

    @pytest.mark.asyncio
    async def test_delete_user_no_auth_token(
        self,
        async_client: AsyncClient,
        override_get_db: None,
    ) -> None:
        """Test deleting without auth token returns 403."""
        fake_id = str(uuid4())

        response = await async_client.delete(f"/users/{fake_id}")

        assert response.status_code == HTTPStatus.FORBIDDEN
        data = response.json()
        assert "unauthorized" in data["detail"].lower()

    @pytest.mark.asyncio
    async def test_delete_user_invalid_auth_token(
        self,
        async_client: AsyncClient,
        override_get_db: None,
    ) -> None:
        """Test deleting with wrong auth token returns 403."""
        fake_id = str(uuid4())

        response = await async_client.delete(
            f"/users/{fake_id}", headers={"X-Auth-Token": "wrong-token"}
        )

        assert response.status_code == HTTPStatus.FORBIDDEN
        data = response.json()
        assert "unauthorized" in data["detail"].lower()

    @pytest.mark.asyncio
    async def test_delete_user_invalid_id_format(
        self,
        async_client: AsyncClient,
        override_get_db: None,
    ) -> None:
        """Test deleting with invalid user ID format returns 400."""
        response = await async_client.delete(
            "/users/not-a-uuid", headers={"X-Auth-Token": AUTH_TOKEN}
        )

        assert response.status_code == HTTPStatus.BAD_REQUEST
        data = response.json()
        assert "detail" in data
