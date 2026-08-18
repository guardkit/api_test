"""Tests for the recent-users endpoint."""

from __future__ import annotations

from http import HTTPStatus

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.users import crud
from src.users.schemas import UserCreate


class TestRecentUsersEndpoint:
    """Tests for GET /recent-users endpoint."""

    @pytest.mark.asyncio
    async def test_recent_users_empty(
        self, async_client: AsyncClient, override_get_db: None
    ) -> None:
        """Test that empty database returns empty list."""
        response = await async_client.get("/recent-users")

        assert response.status_code == HTTPStatus.OK
        data = response.json()
        assert data["users"] == []
        assert data["total"] == 0

    @pytest.mark.asyncio
    async def test_recent_users_default_limit(
        self, async_client: AsyncClient, override_get_db: None, db_session: AsyncSession
    ) -> None:
        """Test default limit of 10 users."""
        # Create 15 users
        for i in range(15):
            await crud.create_user(
                db_session,
                UserCreate(
                    email=f"user{i}@example.com", full_name=f"User {i}"
                ),
            )
        await db_session.commit()

        response = await async_client.get("/recent-users")

        assert response.status_code == HTTPStatus.OK
        data = response.json()
        assert data["total"] == 10
        assert len(data["users"]) == 10

    @pytest.mark.asyncio
    async def test_recent_users_custom_limit(
        self, async_client: AsyncClient, override_get_db: None, db_session: AsyncSession
    ) -> None:
        """Test custom limit parameter."""
        # Create 5 users
        for i in range(5):
            await crud.create_user(
                db_session,
                UserCreate(
                    email=f"user{i}@example.com", full_name=f"User {i}"
                ),
            )
        await db_session.commit()

        response = await async_client.get("/recent-users?limit=3")

        assert response.status_code == HTTPStatus.OK
        data = response.json()
        assert data["total"] == 3
        assert len(data["users"]) == 3

    @pytest.mark.asyncio
    async def test_recent_users_descending_order(
        self, async_client: AsyncClient, override_get_db: None, db_session: AsyncSession
    ) -> None:
        """Test that users are returned in descending order by created_at."""
        import asyncio

        # Create users with small delays to ensure distinct timestamps
        for i in range(5):
            await crud.create_user(
                db_session,
                UserCreate(
                    email=f"desc_user{i}@example.com", full_name=f"Desc User {i}"
                ),
            )
            if i < 4:
                await asyncio.sleep(0.05)
        await db_session.commit()

        response = await async_client.get("/recent-users?limit=5")

        assert response.status_code == HTTPStatus.OK
        data = response.json()
        assert len(data["users"]) == 5
        # Verify created_at timestamps are in descending order
        timestamps = [user["created_at"] for user in data["users"]]
        assert timestamps == sorted(timestamps, reverse=True)

    @pytest.mark.asyncio
    async def test_recent_users_limit_capped_at_100(
        self, async_client: AsyncClient, override_get_db: None, db_session: AsyncSession
    ) -> None:
        """Test that limit is capped at 100."""
        # Create 200 users
        for i in range(200):
            await crud.create_user(
                db_session,
                UserCreate(
                    email=f"cap_user{i}@example.com", full_name=f"Cap User {i}"
                ),
            )
        await db_session.commit()

        response = await async_client.get("/recent-users?limit=200")

        assert response.status_code == HTTPStatus.OK
        data = response.json()
        assert data["total"] == 100
        assert len(data["users"]) == 100

    @pytest.mark.asyncio
    async def test_recent_users_response_format(
        self, async_client: AsyncClient, override_get_db: None, db_session: AsyncSession
    ) -> None:
        """Test that response contains required user fields."""
        await crud.create_user(
            db_session,
            UserCreate(
                email="format_test@example.com", full_name="Format Test"
            ),
        )
        await db_session.commit()

        response = await async_client.get("/recent-users")

        assert response.status_code == HTTPStatus.OK
        data = response.json()
        user = data["users"][0]
        assert "id" in user
        assert "email" in user
        assert "full_name" in user
        assert "is_active" in user
        assert "created_at" in user
        assert "updated_at" in user
        assert user["email"] == "format_test@example.com"
        assert user["full_name"] == "Format Test"
        assert user["is_active"] is True
