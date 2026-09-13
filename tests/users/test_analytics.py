"""Integration tests for the daily user creation counts analytics endpoint.

Covers the GET /users/created-per-day endpoint with tests for:
- Exact 7-day response with correct ordering (AC-001)
- Systems running for fewer than 7 days (AC-002)
- Error responses for invalid requests (AC-003)
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from http import HTTPStatus
from unittest.mock import patch

from httpx import AsyncClient
from sqlalchemy.exc import SQLAlchemyError

from src.users import crud
from src.users.schemas import UserCreate


class TestAnalyticsSevenDayResponse:
    """AC-001: Test returns exactly 7 days of data ordered oldest first."""

    async def test_returns_exactly_7_data_points(
        self, async_client: AsyncClient, override_get_db: None
    ) -> None:
        """Verify the response contains exactly 7 data points."""
        response = await async_client.get("/users/created-per-day")

        assert response.status_code == HTTPStatus.OK
        data = response.json()
        assert len(data) == 7

    async def test_data_points_ordered_oldest_first(
        self, async_client: AsyncClient, override_get_db: None
    ) -> None:
        """Verify data points are ordered from oldest to newest."""
        response = await async_client.get("/users/created-per-day")

        data = response.json()
        dates = [point["date"] for point in data]
        assert dates == sorted(dates), "Data points must be ordered oldest first"

    async def test_first_day_is_six_days_ago(
        self, async_client: AsyncClient, override_get_db: None
    ) -> None:
        """Verify the first data point covers 6 days ago."""
        response = await async_client.get("/users/created-per-day")

        data = response.json()
        expected_first = (date.today() - timedelta(days=6)).isoformat()
        assert data[0]["date"] == expected_first

    async def test_last_day_is_today(
        self, async_client: AsyncClient, override_get_db: None
    ) -> None:
        """Verify the last data point covers today."""
        response = await async_client.get("/users/created-per-day")

        data = response.json()
        assert data[-1]["date"] == date.today().isoformat()

    async def test_all_dates_contiguous_no_gaps(
        self, async_client: AsyncClient, override_get_db: None
    ) -> None:
        """Verify all 7 dates are contiguous with no gaps."""
        response = await async_client.get("/users/created-per-day")

        data = response.json()
        dates = [date.fromisoformat(point["date"]) for point in data]
        for i in range(1, len(dates)):
            assert (dates[i] - dates[i - 1]).days == 1

    async def test_each_point_has_date_and_count_fields(
        self, async_client: AsyncClient, override_get_db: None
    ) -> None:
        """Verify each data point has the expected schema fields."""
        response = await async_client.get("/users/created-per-day")

        data = response.json()
        for point in data:
            assert "date" in point
            assert "count" in point
            assert isinstance(point["date"], str)
            assert isinstance(point["count"], int)

    async def test_counts_are_non_negative(
        self, async_client: AsyncClient, override_get_db: None
    ) -> None:
        """Verify all counts are non-negative integers."""
        response = await async_client.get("/users/created-per-day")

        data = response.json()
        for point in data:
            assert point["count"] >= 0


class TestAnalyticsShortSystem:
    """AC-002: Test handles systems running for less than 7 days correctly."""

    async def test_empty_system_returns_7_zero_count_days(
        self, async_client: AsyncClient, override_get_db: None
    ) -> None:
        """Verify an empty system returns 7 days with zero counts."""
        response = await async_client.get("/users/created-per-day")

        data = response.json()
        assert len(data) == 7
        for point in data:
            assert point["count"] == 0

    async def test_recent_users_only_populate_recent_days(
        self, async_client: AsyncClient, db_session, override_get_db: None
    ) -> None:
        """Verify only days with user creations show non-zero counts."""
        # Create users only on the last 2 days
        today = date.today()
        for day_offset in [0, 1]:
            target_day = today - timedelta(days=day_offset)
            target_dt = datetime(
                target_day.year, target_day.month, target_day.day, 12, 0, 0
            )
            user_in = UserCreate(
                email=f"recent-{day_offset}@example.com",
                full_name=f"Recent User {day_offset}",
            )
            user = await crud.create_user(db_session, user_in)
            user.created_at = target_dt
            await db_session.flush()
            await db_session.refresh(user)

        response = await async_client.get("/users/created-per-day")

        data = response.json()
        assert len(data) == 7
        # Days 0 and 1 (today and yesterday) should have count 1
        # Days 2-6 should have count 0
        for day_offset in [0, 1]:
            idx = 6 - day_offset
            assert data[idx]["count"] == 1
        for day_offset in range(2, 7):
            idx = 6 - day_offset
            assert data[idx]["count"] == 0

    async def test_system_running_3_days_returns_7_days_with_zeros(
        self, async_client: AsyncClient, db_session, override_get_db: None
    ) -> None:
        """Verify a 3-day-old system still returns 7 data points."""
        # Create users on the last 3 days only
        today = date.today()
        for day_offset in [0, 1, 2]:
            target_day = today - timedelta(days=day_offset)
            target_dt = datetime(
                target_day.year, target_day.month, target_day.day, 12, 0, 0
            )
            user_in = UserCreate(
                email=f"three-day-{day_offset}@example.com",
                full_name=f"Three Day User {day_offset}",
            )
            user = await crud.create_user(db_session, user_in)
            user.created_at = target_dt
            await db_session.flush()
            await db_session.refresh(user)

        response = await async_client.get("/users/created-per-day")

        data = response.json()
        assert len(data) == 7
        # First 4 days (7,6,5,4 ago) should be zero
        for day_offset in range(3, 7):
            idx = 6 - day_offset
            assert data[idx]["count"] == 0

    async def test_single_user_on_oldest_day(
        self, async_client: AsyncClient, db_session, override_get_db: None
    ) -> None:
        """Verify a user created 6 days ago shows correctly."""
        target_day = date.today() - timedelta(days=6)
        target_dt = datetime(
            target_day.year, target_day.month, target_day.day, 12, 0, 0
        )
        user_in = UserCreate(
            email="oldest@example.com",
            full_name="Oldest User",
        )
        user = await crud.create_user(db_session, user_in)
        user.created_at = target_dt
        await db_session.flush()
        await db_session.refresh(user)

        response = await async_client.get("/users/created-per-day")

        data = response.json()
        assert data[0]["date"] == target_day.isoformat()
        assert data[0]["count"] == 1
        for point in data[1:]:
            assert point["count"] == 0


class TestAnalyticsErrorResponses:
    """AC-003: Test verifies error responses for invalid requests."""

    async def test_returns_503_when_database_unavailable(
        self, async_client: AsyncClient, override_get_db: None
    ) -> None:
        """Verify 503 Service Unavailable when database fails."""
        with patch.object(crud, "user_creation_count") as mock_count:
            mock_count.side_effect = SQLAlchemyError("Connection refused")

            response = await async_client.get("/users/created-per-day")

            assert response.status_code == HTTPStatus.SERVICE_UNAVAILABLE
            data = response.json()
            assert "detail" in data
            assert "Database unavailable" in data["detail"]

    async def test_rejects_post_method_with_405(
        self, async_client: AsyncClient
    ) -> None:
        """Verify POST to the endpoint returns 405 Method Not Allowed."""
        response = await async_client.post("/users/created-per-day")

        assert response.status_code == HTTPStatus.METHOD_NOT_ALLOWED

    async def test_rejects_put_method_with_error(
        self, async_client: AsyncClient
    ) -> None:
        """Verify PUT to the endpoint returns an error response."""
        response = await async_client.put("/users/created-per-day")

        assert response.status_code >= HTTPStatus.BAD_REQUEST

    async def test_rejects_delete_method_with_error(
        self, async_client: AsyncClient
    ) -> None:
        """Verify DELETE to the endpoint returns an error response."""
        response = await async_client.delete("/users/created-per-day")

        assert response.status_code >= HTTPStatus.BAD_REQUEST

    async def test_returns_json_error_body_on_503(
        self, async_client: AsyncClient, override_get_db: None
    ) -> None:
        """Verify error responses have a valid JSON body with detail field."""
        with patch.object(crud, "user_creation_count") as mock_count:
            mock_count.side_effect = SQLAlchemyError("Timeout")

            response = await async_client.get("/users/created-per-day")

            assert response.status_code == HTTPStatus.SERVICE_UNAVAILABLE
            data = response.json()
            assert isinstance(data, dict)
            assert "detail" in data
            assert isinstance(data["detail"], str)
            assert len(data["detail"]) > 0
