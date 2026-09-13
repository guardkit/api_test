"""Tests for the GET /users/created-per-day endpoint."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from http import HTTPStatus
from unittest.mock import patch

from httpx import AsyncClient
from sqlalchemy.exc import SQLAlchemyError

from src.users import crud
from src.users.schemas import UserCreate


class TestCreatedPerDayEndpoint:
    """Tests for the GET /users/created-per-day endpoint."""

    async def test_returns_200_with_exactly_7_data_points(
        self, async_client: AsyncClient, override_get_db: None
    ) -> None:
        """AC-001: GET /users/created-per-day returns 200 OK with correct data."""
        response = await async_client.get("/users/created-per-day")

        assert response.status_code == HTTPStatus.OK
        data = response.json()
        assert len(data) == 7

    async def test_returns_data_points_when_no_users_exist(
        self, async_client: AsyncClient, override_get_db: None
    ) -> None:
        """AC-001: Returns zero counts for all 7 days when no users exist."""
        response = await async_client.get("/users/created-per-day")

        assert response.status_code == HTTPStatus.OK
        data = response.json()
        assert len(data) == 7
        for point in data:
            assert point["count"] == 0

    async def test_each_data_point_has_date_and_count(
        self, async_client: AsyncClient, override_get_db: None
    ) -> None:
        """AC-002: Response format matches the schema with date and count fields."""
        response = await async_client.get("/users/created-per-day")

        data = response.json()
        for point in data:
            assert "date" in point
            assert "count" in point
            assert isinstance(point["date"], str)
            assert isinstance(point["count"], int)

    async def test_data_points_ordered_oldest_to_newest(
        self, async_client: AsyncClient, override_get_db: None
    ) -> None:
        """AC-002: Data points are ordered oldest to newest."""
        response = await async_client.get("/users/created-per-day")

        data = response.json()
        dates = [point["date"] for point in data]
        assert dates == sorted(dates)

    async def test_last_day_is_today(
        self, async_client: AsyncClient, override_get_db: None
    ) -> None:
        """The last data point should be today."""
        response = await async_client.get("/users/created-per-day")

        data = response.json()
        assert data[-1]["date"] == date.today().isoformat()

    async def test_first_day_is_six_days_ago(
        self, async_client: AsyncClient, override_get_db: None
    ) -> None:
        """The first data point should be 6 days ago."""
        response = await async_client.get("/users/created-per-day")

        data = response.json()
        expected_first = (date.today() - timedelta(days=6)).isoformat()
        assert data[0]["date"] == expected_first

    async def test_counts_users_created_on_specific_day(
        self, async_client: AsyncClient, db_session, override_get_db: None
    ) -> None:
        """Test that counts match actual user creations on a specific day."""
        today = date.today()
        target_day = today - timedelta(days=3)
        target_dt = datetime(
            target_day.year, target_day.month, target_day.day, 12, 0, 0
        )

        # Create 3 users on the target day
        for i in range(3):
            user_in = UserCreate(
                email=f"day3-{i}@example.com",
                full_name=f"Day 3 User {i}",
            )
            user = await crud.create_user(db_session, user_in)
            user.created_at = target_dt
            await db_session.flush()
            await db_session.refresh(user)

        response = await async_client.get("/users/created-per-day")

        data = response.json()
        target_index = 3  # 6 days ago = index 0, today = index 6, 3 days ago = index 3
        assert data[target_index]["date"] == target_day.isoformat()
        assert data[target_index]["count"] == 3

    async def test_counts_users_created_on_multiple_days(
        self, async_client: AsyncClient, db_session, override_get_db: None
    ) -> None:
        """Test counts across multiple days with different numbers of users."""
        today = date.today()

        # Create users on different days
        for day_offset, count in [(0, 2), (2, 5), (5, 1)]:
            target_day = today - timedelta(days=day_offset)
            target_dt = datetime(
                target_day.year, target_day.month, target_day.day, 12, 0, 0
            )
            for i in range(count):
                user_in = UserCreate(
                    email=f"day{day_offset}-{i}@example.com",
                    full_name=f"Day {day_offset} User {i}",
                )
                user = await crud.create_user(db_session, user_in)
                user.created_at = target_dt
                await db_session.flush()
                await db_session.refresh(user)

        response = await async_client.get("/users/created-per-day")

        data = response.json()
        for day_offset, expected_count in [(0, 2), (2, 5), (5, 1)]:
            idx = 6 - day_offset  # index 6 = today, index 0 = 6 days ago
            assert data[idx]["date"] == (today - timedelta(days=day_offset)).isoformat()
            assert data[idx]["count"] == expected_count

    async def test_missing_days_have_zero_count(
        self, async_client: AsyncClient, db_session, override_get_db: None
    ) -> None:
        """Test that days with no user creations show count of zero."""
        today = date.today()

        # Create users only on today and 5 days ago
        for day_offset in [0, 5]:
            target_day = today - timedelta(days=day_offset)
            target_dt = datetime(
                target_day.year, target_day.month, target_day.day, 12, 0, 0
            )
            user_in = UserCreate(
                email=f"sparse-{day_offset}@example.com",
                full_name=f"Sparse User {day_offset}",
            )
            user = await crud.create_user(db_session, user_in)
            user.created_at = target_dt
            await db_session.flush()
            await db_session.refresh(user)

        response = await async_client.get("/users/created-per-day")

        data = response.json()
        # Days 1, 2, 3, 4 should have zero count
        for day_offset in [1, 2, 3, 4]:
            idx = 6 - day_offset
            assert data[idx]["count"] == 0


class TestCreatedPerDayErrorHandling:
    """Tests for error scenarios in the /users/created-per-day endpoint."""

    async def test_returns_503_when_db_unavailable(
        self, async_client: AsyncClient, override_get_db: None
    ) -> None:
        """AC-003: Endpoint handles service unavailability gracefully.

        Verifies that SQLAlchemyError raised during user_creation_count is
        translated to HTTP 503 Service Unavailable with an appropriate
        error detail message.
        """
        with patch.object(crud, "user_creation_count") as mock_count:
            mock_count.side_effect = SQLAlchemyError("Database connection failed")

            response = await async_client.get("/users/created-per-day")

            assert response.status_code == HTTPStatus.SERVICE_UNAVAILABLE
            data = response.json()
            assert "Database unavailable" in data["detail"]

    async def test_rejects_post_with_invalid_method(
        self, async_client: AsyncClient
    ) -> None:
        """Test that POST to /users/created-per-day returns 405 Method Not Allowed."""
        response = await async_client.post("/users/created-per-day")

        assert response.status_code == HTTPStatus.METHOD_NOT_ALLOWED
