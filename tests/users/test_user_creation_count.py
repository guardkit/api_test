"""Tests for the user_creation_count CRUD function."""

from __future__ import annotations

from datetime import date, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from src.users import crud
from src.users.schemas import UserCreate


class TestUserCreationCountBasic:
    """Basic tests for user_creation_count."""

    async def test_returns_exactly_7_data_points(
        self, db_session: AsyncSession
    ) -> None:
        """AC-001: Query returns exactly 7 data points for the last 7 days."""
        result = await crud.user_creation_count(db_session)

        assert len(result) == 7

    async def test_returns_data_points_when_no_users_exist(
        self, db_session: AsyncSession
    ) -> None:
        """AC-004: Returns zero counts for all 7 days when no users exist."""
        result = await crud.user_creation_count(db_session)

        assert len(result) == 7
        for point in result:
            assert point["count"] == 0

    async def test_each_data_point_has_date_and_count(
        self, db_session: AsyncSession
    ) -> None:
        """AC-003: Each data point includes a date and a count."""
        result = await crud.user_creation_count(db_session)

        for point in result:
            assert "date" in point
            assert "count" in point
            assert isinstance(point["date"], date)
            assert isinstance(point["count"], int)


class TestUserCreationCountOrdering:
    """Tests for ordering of data points."""

    async def test_ordered_oldest_to_newest(self, db_session: AsyncSession) -> None:
        """AC-002: Data points are ordered oldest to newest."""
        result = await crud.user_creation_count(db_session)

        dates = [point["date"] for point in result]
        assert dates == sorted(dates)

    async def test_last_day_is_today(self, db_session: AsyncSession) -> None:
        """The last data point should be today."""
        result = await crud.user_creation_count(db_session)

        assert result[-1]["date"] == date.today()

    async def test_first_day_is_six_days_ago(self, db_session: AsyncSession) -> None:
        """The first data point should be 6 days ago."""
        result = await crud.user_creation_count(db_session)

        assert result[0]["date"] == date.today() - timedelta(days=6)


class TestUserCreationCountWithData:
    """Tests for user_creation_count with actual user data."""

    async def test_counts_users_created_on_specific_day(
        self, db_session: AsyncSession
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

        result = await crud.user_creation_count(db_session)

        target_index = 3  # 6 days ago = index 0, today = index 6, 3 days ago = index 3
        assert result[target_index]["date"] == target_day
        assert result[target_index]["count"] == 3

    async def test_counts_users_created_on_multiple_days(
        self, db_session: AsyncSession
    ) -> None:
        """Test counts across multiple days."""
        today = date.today()

        # Create 2 users 5 days ago
        day_5 = today - timedelta(days=5)
        day_5_dt = datetime(day_5.year, day_5.month, day_5.day, 10, 0, 0)
        for i in range(2):
            user_in = UserCreate(
                email=f"day5-{i}@example.com",
                full_name=f"Day 5 User {i}",
            )
            user = await crud.create_user(db_session, user_in)
            user.created_at = day_5_dt
            await db_session.flush()
            await db_session.refresh(user)

        # Create 4 users today
        today_dt = datetime(today.year, today.month, today.day, 15, 0, 0)
        for i in range(4):
            user_in = UserCreate(
                email=f"today-{i}@example.com",
                full_name=f"Today User {i}",
            )
            user = await crud.create_user(db_session, user_in)
            user.created_at = today_dt
            await db_session.flush()
            await db_session.refresh(user)

        result = await crud.user_creation_count(db_session)

        # 5 days ago = index 1 (6 days ago is index 0)
        assert result[1]["date"] == day_5
        assert result[1]["count"] == 2

        # Today = index 6
        assert result[6]["date"] == today
        assert result[6]["count"] == 4

        # Days in between should be zero
        for i in [2, 3, 4, 5]:
            assert result[i]["count"] == 0

    async def test_multiple_users_same_day_counted_correctly(
        self, db_session: AsyncSession
    ) -> None:
        """Test that multiple users created on the same day are counted correctly."""
        today = date.today()
        today_dt = datetime(today.year, today.month, today.day, 12, 0, 0)

        for i in range(10):
            user_in = UserCreate(
                email=f"bulk-{i}@example.com",
                full_name=f"Bulk User {i}",
            )
            user = await crud.create_user(db_session, user_in)
            user.created_at = today_dt
            await db_session.flush()
            await db_session.refresh(user)

        result = await crud.user_creation_count(db_session)

        assert result[6]["count"] == 10


class TestUserCreationCountEdgeCases:
    """Edge case tests for user_creation_count."""

    async def test_handles_users_created_at_midnight(
        self, db_session: AsyncSession
    ) -> None:
        """Test that users created exactly at 00:00:00 are counted."""
        today = date.today()
        midnight = datetime(today.year, today.month, today.day, 0, 0, 0)

        user_in = UserCreate(
            email="midnight@example.com",
            full_name="Midnight User",
        )
        user = await crud.create_user(db_session, user_in)
        user.created_at = midnight
        await db_session.flush()
        await db_session.refresh(user)

        result = await crud.user_creation_count(db_session)
        assert result[6]["count"] == 1

    async def test_handles_users_created_at_end_of_day(
        self, db_session: AsyncSession
    ) -> None:
        """Test that users created at 23:59:59 are counted."""
        today = date.today()
        end_of_day = datetime(today.year, today.month, today.day, 23, 59, 59)

        user_in = UserCreate(
            email="endofday@example.com",
            full_name="End of Day User",
        )
        user = await crud.create_user(db_session, user_in)
        user.created_at = end_of_day
        await db_session.flush()
        await db_session.refresh(user)

        result = await crud.user_creation_count(db_session)
        assert result[6]["count"] == 1

    async def test_excludes_deleted_users(self, db_session: AsyncSession) -> None:
        """Test that soft-deleted users are excluded from counts."""
        from datetime import UTC

        today = date.today()
        today_dt = datetime(today.year, today.month, today.day, 12, 0, 0)

        # Create a user
        user_in = UserCreate(
            email="deleted@example.com",
            full_name="Deleted User",
        )
        user = await crud.create_user(db_session, user_in)
        user.created_at = today_dt
        await db_session.flush()
        await db_session.refresh(user)

        # Soft-delete the user
        user.deleted_at = datetime.now(UTC)
        await db_session.flush()
        await db_session.refresh(user)

        result = await crud.user_creation_count(db_session)
        assert result[6]["count"] == 0

    async def test_excludes_users_created_outside_window(
        self, db_session: AsyncSession
    ) -> None:
        """Test that users created outside the 7-day window are excluded."""
        today = date.today()
        # Create a user 8 days ago (outside the window)
        old_day = today - timedelta(days=8)
        old_dt = datetime(old_day.year, old_day.month, old_day.day, 12, 0, 0)

        user_in = UserCreate(
            email="old@example.com",
            full_name="Old User",
        )
        user = await crud.create_user(db_session, user_in)
        user.created_at = old_dt
        await db_session.flush()
        await db_session.refresh(user)

        # Also create a user tomorrow (outside the window)
        future_day = today + timedelta(days=1)
        future_dt = datetime(
            future_day.year, future_day.month, future_day.day, 12, 0, 0
        )

        future_user_in = UserCreate(
            email="future@example.com",
            full_name="Future User",
        )
        future_user = await crud.create_user(db_session, future_user_in)
        future_user.created_at = future_dt
        await db_session.flush()
        await db_session.refresh(future_user)

        result = await crud.user_creation_count(db_session)

        # All counts should be zero since both users are outside the window
        for point in result:
            assert point["count"] == 0

    async def test_handles_system_running_less_than_7_days(
        self, db_session: AsyncSession
    ) -> None:
        """AC-004: Returns zero counts for days before system started."""
        today = date.today()
        # Create a user only 2 days ago
        two_days_ago = today - timedelta(days=2)
        two_days_dt = datetime(
            two_days_ago.year, two_days_ago.month, two_days_ago.day, 12, 0, 0
        )

        user_in = UserCreate(
            email="newuser@example.com",
            full_name="New User",
        )
        user = await crud.create_user(db_session, user_in)
        user.created_at = two_days_dt
        await db_session.flush()
        await db_session.refresh(user)

        result = await crud.user_creation_count(db_session)

        # Should still return 7 data points
        assert len(result) == 7

        # Days 0-3 (6, 5, 4, 3 days ago) should be zero
        for i in range(4):
            assert result[i]["count"] == 0

        # Days 4-6 (2, 1, 0 days ago) should have counts
        assert result[4]["count"] == 1  # 2 days ago
        assert result[5]["count"] == 0  # 1 day ago
        assert result[6]["count"] == 0  # today
