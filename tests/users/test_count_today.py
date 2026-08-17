"""Tests for the /users/count-today endpoint and count_users_today CRUD function."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from http import HTTPStatus

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.users import crud
from src.users.schemas import UserCreate


class TestCountUsersTodayCrud:
    """Tests for the count_users_today CRUD function."""

    async def test_count_users_today_empty(self, db_session: AsyncSession) -> None:
        """Test count when no users exist."""
        count = await crud.count_users_today(db_session)
        assert count == 0

    async def test_count_users_today_with_today_users(
        self, db_session: AsyncSession
    ) -> None:
        """Test count includes users created today."""
        # Create users with today's date
        today = date.today()
        now = datetime(today.year, today.month, today.day, 12, 0, 0, tzinfo=UTC)

        user_in = UserCreate(email="today@example.com", full_name="Today User")
        user = await crud.create_user(db_session, user_in)

        # Override created_at to today
        user.created_at = now
        await db_session.flush()
        await db_session.refresh(user)

        count = await crud.count_users_today(db_session)
        assert count == 1

    async def test_count_users_today_excludes_yesterday(
        self, db_session: AsyncSession
    ) -> None:
        """Test count excludes users created yesterday."""
        today = date.today()
        yesterday = today - timedelta(days=1)
        yesterday_dt = datetime(
            yesterday.year, yesterday.month, yesterday.day, 12, 0, 0, tzinfo=UTC
        )

        user_in = UserCreate(email="yesterday@example.com", full_name="Yesterday User")
        user = await crud.create_user(db_session, user_in)

        # Override created_at to yesterday
        user.created_at = yesterday_dt
        await db_session.flush()
        await db_session.refresh(user)

        count = await crud.count_users_today(db_session)
        assert count == 0


class TestCountTodayEndpoint:
    """Tests for GET /users/count-today endpoint."""

    @pytest.mark.asyncio
    async def test_count_today_returns_200(
        self, async_client: AsyncClient, override_get_db: None
    ) -> None:
        """Test that the endpoint returns 200 OK."""
        response = await async_client.get("/users/count-today")

        assert response.status_code == HTTPStatus.OK
        data = response.json()
        assert "count" in data
        assert isinstance(data["count"], int)

    @pytest.mark.asyncio
    async def test_count_today_empty_db(
        self, async_client: AsyncClient, override_get_db: None
    ) -> None:
        """Test count returns 0 when no users exist."""
        response = await async_client.get("/users/count-today")

        assert response.status_code == HTTPStatus.OK
        data = response.json()
        assert data["count"] == 0

    @pytest.mark.asyncio
    async def test_count_today_with_users_today(
        self, async_client: AsyncClient, override_get_db: None, db_session: AsyncSession
    ) -> None:
        """Test count includes users created today."""
        # Create a user
        user_in = UserCreate(email="today@example.com", full_name="Today User")
        await crud.create_user(db_session, user_in)

        response = await async_client.get("/users/count-today")

        assert response.status_code == HTTPStatus.OK
        data = response.json()
        assert data["count"] >= 1

    @pytest.mark.asyncio
    async def test_count_today_response_json_structure(
        self, async_client: AsyncClient, override_get_db: None
    ) -> None:
        """Test that the response body is { "count": N }."""
        response = await async_client.get("/users/count-today")

        assert response.status_code == HTTPStatus.OK
        data = response.json()
        assert set(data.keys()) == {"count"}
        assert isinstance(data["count"], int)
