"""Tests for the /users/created-per-day endpoint and CRUD."""

from __future__ import annotations

from datetime import date, datetime, timedelta

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from src.users import crud
from src.users.schemas import UserCreate


class TestCountUsersCreatedPerDay:
    """Tests for the count_users_created_per_day CRUD function."""

    async def test_returns_exactly_seven_days(self, db_session: AsyncSession) -> None:
        """AC-001: Test returns exactly seven days of data.

        Verify that count_users_created_per_day returns exactly 7 data points
        regardless of how many users exist in the database.
        """
        result = await crud.count_users_created_per_day(db_session)
        assert len(result) == 7

    async def test_oldest_to_newest_ordering(self, db_session: AsyncSession) -> None:
        """AC-002: Test verifies oldest-to-newest ordering.

        Verify that the 7 data points are ordered from oldest (6 days ago)
        to newest (today).
        """
        result = await crud.count_users_created_per_day(db_session)
        assert len(result) == 7

        today = date.today()
        for i, entry in enumerate(result):
            expected_date = today - timedelta(days=6 - i)
            assert entry["date"] == expected_date.isoformat()

    async def test_zero_count_days_included(self, db_session: AsyncSession) -> None:
        """AC-003: Test verifies zero-count days are included.

        Verify that days with no users are still included in the response
        with a count of zero.
        """
        result = await crud.count_users_created_per_day(db_session)
        for entry in result:
            assert entry["count"] >= 0
        # With empty DB all counts should be zero
        for entry in result:
            assert entry["count"] == 0

    async def test_with_users_on_specific_day(self, db_session: AsyncSession) -> None:
        """Test that users created on a specific day are counted correctly."""
        today = date.today()

        # Create a user 3 days ago
        three_days_ago = today - timedelta(days=3)
        user_time = datetime(
            three_days_ago.year,
            three_days_ago.month,
            three_days_ago.day,
            12,
            0,
            0,
        )
        user_in = UserCreate(
            email="specific-day@example.com",
            full_name="Specific Day User",
        )
        user = await crud.create_user(db_session, user_in)
        user.created_at = user_time
        await db_session.flush()

        result = await crud.count_users_created_per_day(db_session)
        assert len(result) == 7

        # Find the entry for 3 days ago
        three_days_entry = None
        for entry in result:
            if entry["date"] == three_days_ago.isoformat():
                three_days_entry = entry
                break

        assert three_days_entry is not None
        assert three_days_entry["count"] == 1

    async def test_with_users_on_multiple_days(self, db_session: AsyncSession) -> None:
        """Test counting across multiple days with varying user counts."""
        today = date.today()

        # Create users on different days
        for day_offset in [0, 2, 5]:
            target_date = today - timedelta(days=day_offset)
            user_time = datetime(
                target_date.year,
                target_date.month,
                target_date.day,
                10,
                0,
                0,
            )
            for i in range(3):
                user_in = UserCreate(
                    email=f"multi-day-{day_offset}-{i}@example.com",
                    full_name=f"Multi Day User {day_offset} {i}",
                )
                user = await crud.create_user(db_session, user_in)
                user.created_at = user_time
                await db_session.flush()

        result = await crud.count_users_created_per_day(db_session)
        assert len(result) == 7

        # Verify counts for days with users
        for entry in result:
            entry_date = date.fromisoformat(entry["date"])
            days_ago = (today - entry_date).days
            if days_ago in [0, 2, 5]:
                assert entry["count"] == 3
            else:
                assert entry["count"] == 0

    async def test_oldest_day_is_six_days_ago(self, db_session: AsyncSession) -> None:
        """Test that the oldest day in the response is exactly 6 days before today."""
        result = await crud.count_users_created_per_day(db_session)
        assert len(result) == 7

        oldest = date.fromisoformat(result[0]["date"])
        today = date.today()
        expected_oldest = today - timedelta(days=6)
        assert oldest == expected_oldest

    async def test_newest_day_is_today(self, db_session: AsyncSession) -> None:
        """Test that the newest day in the response is today."""
        result = await crud.count_users_created_per_day(db_session)
        assert len(result) == 7

        newest = date.fromisoformat(result[-1]["date"])
        assert newest == date.today()


class TestCreatedPerDayEndpoint:
    """Tests for the GET /users/created-per-day endpoint."""

    async def test_endpoint_returns_seven_days(
        self, async_client: AsyncClient, override_get_db: None
    ) -> None:
        """AC-001: Endpoint returns exactly seven days of data."""
        response = await async_client.get("/users/created-per-day")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 7

    async def test_endpoint_oldest_to_newest_ordering(
        self, async_client: AsyncClient, override_get_db: None
    ) -> None:
        """AC-002: Endpoint verifies oldest-to-newest ordering."""
        response = await async_client.get("/users/created-per-day")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 7

        today = date.today()
        for i, entry in enumerate(data):
            expected_date = today - timedelta(days=6 - i)
            assert entry["date"] == expected_date.isoformat()

    async def test_endpoint_zero_count_days_included(
        self, async_client: AsyncClient, override_get_db: None
    ) -> None:
        """AC-003: Endpoint verifies zero-count days are included."""
        response = await async_client.get("/users/created-per-day")
        assert response.status_code == 200
        data = response.json()

        for entry in data:
            assert "date" in entry
            assert "count" in entry
            assert isinstance(entry["count"], int)
            assert entry["count"] >= 0

    async def test_endpoint_with_auth_token(
        self, async_client: AsyncClient, override_get_db: None
    ) -> None:
        """Test that the endpoint works with auth token."""
        response = await async_client.get(
            "/users/created-per-day",
            headers={"X-Auth-Token": "dev-token"},
        )
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 7

    async def test_endpoint_post_rejected(
        self, async_client: AsyncClient, override_get_db: None
    ) -> None:
        """Test that POST to the endpoint is rejected."""
        response = await async_client.post("/users/created-per-day")
        # Should be 405 Method Not Allowed since we only defined GET
        assert response.status_code == 405
