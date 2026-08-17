"""Tests for the /users/count-today endpoint and count_users_today CRUD function."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from http import HTTPStatus

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.users import crud
from src.users.schemas import UserCreate


class TestCountTodayBoundaryConditions:
    """Boundary condition tests for the /users/count-today endpoint."""

    # AC-001: Test case for zero users created today
    async def test_count_today_zero_users(self, db_session: AsyncSession) -> None:
        """Test count returns 0 when no users exist at all.

        Zero users created today.
        """
        count = await crud.count_users_today(db_session)
        assert count == 0

    # AC-002: Test case for all users created today
    async def test_count_today_all_users_created_today(
        self, db_session: AsyncSession
    ) -> None:
        """Test count equals total when all users in DB were created today."""
        today = date.today()
        now = datetime(today.year, today.month, today.day, 12, 0, 0, tzinfo=UTC)

        # Create multiple users, all with today's date
        for i in range(3):
            user_in = UserCreate(
                email=f"all-today-{i}@example.com",
                full_name=f"All Today User {i}",
            )
            user = await crud.create_user(db_session, user_in)
            user.created_at = now
            await db_session.flush()
            await db_session.refresh(user)

        # Verify count matches total
        today_count = await crud.count_users_today(db_session)
        total_count = await crud.count_users(db_session)
        assert today_count == total_count
        assert today_count == 3

    # AC-003: Test case for users created at 00:00:00 UTC
    async def test_count_today_user_at_midnight(self, db_session: AsyncSession) -> None:
        """Test that a user created exactly at 00:00:00 UTC today is included."""
        today = date.today()
        midnight = datetime(today.year, today.month, today.day, 0, 0, 0, tzinfo=UTC)

        user_in = UserCreate(
            email="midnight@example.com",
            full_name="Midnight User",
        )
        user = await crud.create_user(db_session, user_in)
        user.created_at = midnight
        await db_session.flush()
        await db_session.refresh(user)

        count = await crud.count_users_today(db_session)
        assert count == 1

    # AC-004: Test case for users created at 23:59:59 UTC
    async def test_count_today_user_at_end_of_day(
        self, db_session: AsyncSession
    ) -> None:
        """Test that a user created exactly at 23:59:59 UTC today is included."""
        today = date.today()
        end_of_day = datetime(
            today.year, today.month, today.day, 23, 59, 59, tzinfo=UTC
        )

        user_in = UserCreate(
            email="endofday@example.com",
            full_name="End of Day User",
        )
        user = await crud.create_user(db_session, user_in)
        user.created_at = end_of_day
        await db_session.flush()
        await db_session.refresh(user)

        count = await crud.count_users_today(db_session)
        assert count == 1

    # Combined boundary: mix of users at boundaries with users outside
    async def test_count_today_boundary_with_excluded_users(
        self, db_session: AsyncSession
    ) -> None:
        """Test boundary conditions with a mix of included and excluded users."""
        today = date.today()
        yesterday = today - timedelta(days=1)
        tomorrow = today + timedelta(days=1)

        # User created yesterday (should be excluded)
        yesterday_dt = datetime(
            yesterday.year, yesterday.month, yesterday.day, 12, 0, 0, tzinfo=UTC
        )
        user_yesterday = await crud.create_user(
            db_session,
            UserCreate(email="yesterday@example.com", full_name="Yesterday"),
        )
        user_yesterday.created_at = yesterday_dt
        await db_session.flush()

        # User created at 00:00:00 UTC today (should be included)
        midnight = datetime(today.year, today.month, today.day, 0, 0, 0, tzinfo=UTC)
        user_midnight = await crud.create_user(
            db_session,
            UserCreate(email="midnight@example.com", full_name="Midnight"),
        )
        user_midnight.created_at = midnight
        await db_session.flush()

        # User created at 23:59:59 UTC today (should be included)
        end_of_day = datetime(
            today.year, today.month, today.day, 23, 59, 59, tzinfo=UTC
        )
        user_eod = await crud.create_user(
            db_session,
            UserCreate(email="endofday@example.com", full_name="End of Day"),
        )
        user_eod.created_at = end_of_day
        await db_session.flush()

        # User created tomorrow (should be excluded)
        tomorrow_dt = datetime(
            tomorrow.year, tomorrow.month, tomorrow.day, 0, 0, 0, tzinfo=UTC
        )
        user_tomorrow = await crud.create_user(
            db_session,
            UserCreate(email="tomorrow@example.com", full_name="Tomorrow"),
        )
        user_tomorrow.created_at = tomorrow_dt
        await db_session.flush()

        count = await crud.count_users_today(db_session)
        assert count == 2  # Only midnight and end_of_day users

    # Endpoint-level boundary: zero users via HTTP
    async def test_count_today_endpoint_zero_users(
        self, async_client: AsyncClient, override_get_db: None
    ) -> None:
        """Test endpoint returns count=0 when no users exist (AC-001 via HTTP)."""
        response = await async_client.get("/users/count-today")
        assert response.status_code == HTTPStatus.OK
        data = response.json()
        assert data["count"] == 0


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
